"""Validation-selected training, matched windows and dimensionless physical losses."""

import math
import os
import pickle
import tempfile
from pathlib import Path
from time import perf_counter

import torch

from .data import indices, load
from .models import Operator, normalize

DEFAULT_LOSS = {"mass": 0.0, "energy": 0.0, "positive": 0.0, "multi": 0.0}


def atomic_save(obj, path):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        name = tmp.name
    try:
        torch.save(obj, name)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_checkpoint(path, m, device="cpu"):
    try:
        ck = torch.load(path, map_location="cpu", weights_only=True)
    except (pickle.UnpicklingError, EOFError) as exc:
        raise ValueError("invalid neural checkpoint") from exc
    if (
        not isinstance(ck, dict)
        or ck.get("format") != 1
        or ck.get("dataset") != m["fingerprint"]
        or not ck.get("history")
    ):
        raise ValueError("untrained checkpoint or incompatible dataset fingerprint")
    model = Operator(**ck["architecture"])
    model.load_state_dict(ck["best"])
    model.to(device).eval()
    return model, ck


def windows(m, states, group, device):
    ids = indices(m, group)
    selection = (
        slice(ids[0], ids[-1] + 1) if ids == list(range(ids[0], ids[-1] + 1)) else ids
    )
    x = torch.tensor(
        normalize(states[selection, : m["train_steps"] + 1], m),
        dtype=torch.float32,
        device=device,
    )
    f = torch.tensor(
        [m["trajectories"][i]["f"] / 1e-4 for i in ids], dtype=x.dtype, device=device
    )
    count = x.shape[1] - 2
    return (
        x[:, :count].flatten(0, 1),
        x[:, 1 : 1 + count].flatten(0, 1),
        x[:, 2:].flatten(0, 1),
        f.repeat_interleave(count),
    )


def physical_loss(pred, target, previous, mean, std, c, weights):
    """Spatial means use constant cell area, which cancels in the normalized penalties."""
    p, t = pred * std + mean, target * std + mean
    h = p[:, 0]
    H, g = c["depth_m"], c["gravity_m_s2"]
    # Penalize signed integral mass change, scaled by the training height variation.
    mass = (pred[:, 0] - previous[:, 0]).mean(dim=(-1, -2)).square().mean()
    positive = (torch.relu(-h) / H).square().mean()

    def energy(state):
        depth, east, north = state.unbind(1)
        return (
            0.5 * (depth * (east.square() + north.square()) + g * (depth - H).square())
        ).mean(dim=(-2, -1))

    scale = 0.5 * (
        g * std[0, 0, 0].square() + H * (std[1, 0, 0].square() + std[2, 0, 0].square())
    )
    energy_error = ((energy(p) - energy(t)) / scale).square().mean()
    return (
        weights["mass"] * mass
        + weights["energy"] * energy_error
        + weights["positive"] * positive
    )


def train(
    dataset,
    checkpoint,
    kind="fno",
    epochs=24,
    seed=11,
    width=12,
    modes=4,
    lr=0.003,
    batch=16,
    patience=8,
    device="cpu",
    weights=None,
    resume=False,
    threads=1,
    depth=2,
):
    path = Path(checkpoint)
    if path.exists() and not resume:
        raise FileExistsError(path)
    weights = DEFAULT_LOSS | (weights or {})
    if (
        set(weights) != set(DEFAULT_LOSS)
        or any(not math.isfinite(v) or v < 0 for v in weights.values())
        or min(epochs, batch, patience, threads) < 1
        or not math.isfinite(lr)
        or lr <= 0
        or seed < 0
    ):
        raise ValueError("invalid training options")
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    m, states = load(dataset)
    arch = {"kind": kind, "width": width, "modes": modes, "depth": depth}
    model = Operator(**arch).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    settings = {
        "seed": seed,
        "batch": batch,
        "lr": lr,
        "weights": weights,
        "device": str(device),
        "threads": threads,
        "patience": patience,
    }
    ck = {
        "format": 1,
        "dataset": m["fingerprint"],
        "architecture": arch,
        "settings": settings,
        "history": [],
        "best_epoch": 0,
        "best_loss": float("inf"),
        "training_s": 0.0,
        "torch": str(torch.__version__),
        "precision": "float32",
    }
    if resume:
        _, ck = read_checkpoint(path, m, device)
        if ({"depth": 2} | ck["architecture"]) != arch or ck["settings"] != settings:
            raise ValueError("resume settings differ")
        model.load_state_dict(ck["last"])
        optimizer.load_state_dict(ck["optimizer"])
    x, y, z, f = windows(m, states, "train", device)
    vx, vy, _, vf = windows(m, states, "validation", device)
    mean, std = (
        torch.tensor(m[k], device=device, dtype=x.dtype)[:, None, None]
        for k in ("mean", "std")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(len(ck["history"]) + 1, epochs + 1):
        if epoch - 1 - ck["best_epoch"] >= patience:
            break
        start = perf_counter()
        model.train()
        total = 0.0
        order = torch.randperm(
            len(x), generator=torch.Generator().manual_seed(seed + epoch)
        )
        for ix in order.split(batch):
            p = model(x[ix], f[ix])
            loss = (p - y[ix]).square().mean()
            if any(weights[k] for k in ("mass", "energy", "positive")):
                loss = loss + physical_loss(
                    p, y[ix], x[ix], mean, std, m["config"], weights
                )
            if weights["multi"]:
                loss = (
                    loss + weights["multi"] * (model(p, f[ix]) - z[ix]).square().mean()
                )
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite training loss")
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(ix)
        model.eval()
        with torch.no_grad():
            # All models selected by the same one-step validation metric.
            val = sum(
                (model(inp, rot) - target).square().mean().item() * len(inp)
                for inp, rot, target in zip(
                    vx.split(batch), vf.split(batch), vy.split(batch), strict=True
                )
            ) / len(vx)
        if not math.isfinite(val):
            raise FloatingPointError("nonfinite validation loss")
        ck["history"].append(
            {"epoch": epoch, "train": total / len(x), "validation": val}
        )
        if val < ck["best_loss"]:
            ck.update(
                best={
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                },
                best_loss=val,
                best_epoch=epoch,
            )
        ck["training_s"] += perf_counter() - start
        ck.update(last=model.state_dict(), optimizer=optimizer.state_dict())
        atomic_save(ck, path)
    return ck
