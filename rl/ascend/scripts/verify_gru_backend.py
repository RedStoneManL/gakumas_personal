"""Verify the CPU lexical GRU bridge on the full checkpoint and real five-phase inputs.

This is a bounded numerical and timing gate, not a model-quality evaluation.
It never modifies the input checkpoint or creates a training checkpoint.
Run in the isolated Ascend deployment after source regression tests.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time


@contextmanager
def backend(name):
    previous = os.environ.get("GAKUMAS_LEXICAL_GRU_BACKEND")
    os.environ["GAKUMAS_LEXICAL_GRU_BACKEND"] = name
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GAKUMAS_LEXICAL_GRU_BACKEND", None)
        else:
            os.environ["GAKUMAS_LEXICAL_GRU_BACKEND"] = previous


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="npu:0")
    parser.add_argument("--torch-threads", type=int, default=4)
    parser.add_argument("--reference", choices=("portable", "cpu", "cpu-buffered"), default="portable")
    parser.add_argument("--candidate", choices=("portable", "cpu", "cpu-buffered"), default="cpu")
    args = parser.parse_args(argv)
    if not args.device.startswith("npu:"):
        parser.error("The cross-device bridge gate requires an NPU, for example npu:0")
    if args.torch_threads < 1:
        parser.error("--torch-threads must be positive")
    if args.output.resolve() == args.initial.resolve():
        parser.error("Report output must differ from the input checkpoint")
    if args.output.exists():
        parser.error("Use a new report path to preserve previous evidence")
    if shutil.which("node") is None:
        parser.error("Node is required for real public-input fixtures")

    exam = args.root / "exam-search"
    if not exam.is_dir():
        exam = args.root / "exam_search"
    training = args.root / "training"
    if not training.is_dir():
        training = args.root.parent / "training"
    sys.path[:0] = [str(exam), str(exam / "tests"), str(exam / "runtime/shared"),
                   str(exam / "runtime/arena"), str(training)]
    import torch
    if args.device.startswith("npu"):
        import torch_npu  # noqa: F401
        torch.npu.set_device(args.device)
    from draftrl.model import DraftPolicy
    from draftrl.fast_collate import collate, prepare_encoded
    from test_relational_runtime import RelationalRuntimeTests

    def synchronize():
        if args.device.startswith("npu"):
            torch.npu.synchronize()

    def vector(parameters, attribute=None):
        values = [getattr(parameter, attribute) if attribute else parameter
                  for parameter in parameters]
        values = [value.detach().reshape(-1) for value in values if value is not None]
        return torch.cat(values).float().cpu()

    started = time.monotonic()
    report = {
        "schema": "arena-lexical-backend-verification/1",
        "device": args.device,
        "reference_backend": args.reference,
        "candidate_backend": args.candidate,
        "checkpoint": str(args.initial.resolve()),
        "source_files": {
            name: hashlib.sha256((exam / "draftrl" / name).read_bytes()).hexdigest()
            for name in ("portable_gru.py", "buffered_gru.py", "fast_collate.py", "model.py",
                         "relational_model.py", "lexical_cache.py")
        },
        "limits": {
            "output_atol": 5e-6, "output_rtol": 2e-5,
            "gradient_max_absolute": 2e-5, "gradient_relative_l2": 1e-4,
            "adam_parameter_max_absolute": 5e-6,
        },
        "quality_validated": False,
    }
    ready = False
    previous_threads = torch.get_num_threads()
    try:
        RelationalRuntimeTests.setUpClass()
        ready = True
        torch.set_num_threads(args.torch_threads)
        fixtures = RelationalRuntimeTests.examples
        examples = [prepare_encoded(copy.deepcopy(encoded))
                    for profile in sorted(fixtures) for encoded in fixtures[profile]]
        phases = sorted({encoded.phase for encoded in examples})
        if phases != list(range(5)):
            raise ValueError("Numerical gate must cover all five public phases")
        report.update(profiles=sorted(fixtures), phases=phases, examples=len(examples),
                      torch_threads=args.torch_threads)
        info = torch.load(args.initial, map_location="cpu", weights_only=True)
        prototype = DraftPolicy(**info["model_config"])
        prototype.load_state_dict(info["model_state"], strict=True)
        # Nonzero side heads ensure the test observes every residual encoder.
        torch.manual_seed(119)
        with torch.no_grad():
            for name, parameter in prototype.named_parameters():
                if (("_relational.policy_heads." in name or "_relational.value_heads." in name
                     or "_relational.quantile_head." in name) and ".2." in name):
                    parameter.normal_(0, .002)
        initial_state = copy.deepcopy(prototype.state_dict())
        batch = collate(examples, args.device)

        def run(name):
            model = DraftPolicy(**info["model_config"])
            model.load_state_dict(initial_state, strict=True)
            model = model.to(args.device)
            parameters = list(model.parameters())
            identities = [id(parameter) for parameter in parameters]
            optimizer = torch.optim.Adam(parameters, lr=5e-4, eps=1e-5, foreach=False)
            synchronize()
            tick = time.monotonic()
            with backend(name):
                logits, values, atoms = model.learning_forward(batch)
                selected = logits[batch["mask"]]
                if atoms is None:
                    raise ValueError("Expected the checkpoint's calibrated quantile head")
                outputs = [selected, values, atoms]
                if not all(bool(torch.isfinite(output).all()) for output in outputs):
                    raise FloatingPointError("Nonfinite full-model output")
                target = torch.sin(torch.arange(selected.numel(), device=args.device) * .013 + .3)
                loss = (selected * target).mean() + values.square().mean() + atoms.square().mean()
                loss.backward()
            synchronize()
            forward_backward_seconds = time.monotonic() - tick
            if identities != [id(parameter) for parameter in model.parameters()]:
                raise RuntimeError("Functional GRU replaced model parameters")
            if not all(parameter.is_leaf and str(parameter.device) == str(torch.device(args.device))
                       for parameter in model.parameters()):
                raise RuntimeError("Optimizer parameters changed leaf status or device")
            grad_names = [key for key, parameter in model.named_parameters() if parameter.grad is not None]
            gradients = vector(parameters, "grad")
            if not bool(torch.isfinite(gradients).all()):
                raise FloatingPointError("Nonfinite gradient")
            outputs = [output.detach().float().cpu() for output in outputs]
            optimizer.step()
            synchronize()
            weights = vector(parameters)
            if not bool(torch.isfinite(weights).all()):
                raise FloatingPointError("Nonfinite Adam result")
            result = dict(outputs=outputs, gradients=gradients, weights=weights,
                          grad_names=grad_names, forward_backward_seconds=forward_backward_seconds)
            del optimizer, model, parameters
            return result

        reference, candidate = run(args.reference), run(args.candidate)
        if reference["grad_names"] != candidate["grad_names"]:
            raise AssertionError("Backend changed which parameters receive gradients")
        output_errors = [float((left-right).abs().max())
                         for left, right in zip(reference["outputs"], candidate["outputs"])]
        gradient_error = candidate["gradients"] - reference["gradients"]
        gradient_max = float(gradient_error.abs().max())
        gradient_relative = float(gradient_error.norm() / reference["gradients"].norm().clamp_min(1e-30))
        weight_error = float((candidate["weights"] - reference["weights"]).abs().max())
        report.update(output_max_absolute=output_errors,
                      gradient_max_absolute=gradient_max,
                      gradient_relative_l2=gradient_relative,
                      adam_parameter_max_absolute=weight_error,
                      parameters_with_gradient=len(candidate["grad_names"]),
                      gradient_elements=candidate["gradients"].numel(),
                      forward_backward_seconds={name: result["forward_backward_seconds"]
                                                for name, result in ((args.reference, reference), (args.candidate, candidate))})
        for left, right in zip(reference["outputs"], candidate["outputs"]):
            torch.testing.assert_close(left, right, atol=5e-6, rtol=2e-5)
        if gradient_max > 2e-5 or gradient_relative > 1e-4:
            raise AssertionError("Full-model gradients exceed the declared FP32 backend error limits")
        if weight_error > 5e-6:
            raise AssertionError("One Adam update exceeds the declared parameter error limit")
        report["passed"] = True
    except Exception as error:
        report.update(passed=False, error=type(error).__name__ + ": " + str(error))
    finally:
        if ready:
            RelationalRuntimeTests.tearDownClass()
        torch.set_num_threads(previous_threads)
        report["elapsed_seconds"] = time.monotonic() - started
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
