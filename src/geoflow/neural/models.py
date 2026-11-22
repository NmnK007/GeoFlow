"""Periodic residual CNN and truncated two-dimensional Fourier operator."""

import torch
from torch import nn
from torch.nn import functional as F


class Spectral(nn.Module):
    def __init__(self, width, modes):
        super().__init__()
        self.modes = modes
        self.weights = nn.Parameter(
            torch.randn(2, width, width, modes, modes, 2) / width
        )

    def forward(self, x):
        m = self.modes
        if 2 * m > x.shape[-2] or m > x.shape[-1] // 2 + 1:
            raise ValueError("Fourier modes exceed grid")
        spectrum = torch.fft.rfft2(x)
        out = torch.zeros_like(spectrum)
        weights = torch.view_as_complex(self.weights.contiguous())
        for side, band in enumerate((slice(0, m), slice(-m, None))):
            out[:, :, band, :m] = torch.einsum(
                "bixy,ioxy->boxy", spectrum[:, :, band, :m], weights[side]
            )
        return torch.fft.irfft2(out, s=x.shape[-2:])


class Operator(nn.Module):
    """Input is normalized (h,u,v) plus a spatially constant f / 1e-4 channel."""

    def __init__(self, kind, width=12, modes=4):
        super().__init__()
        if kind not in ("cnn", "fno") or not 1 <= width <= 128 or not 1 <= modes <= 64:
            raise ValueError("invalid model architecture")
        self.lift = nn.Conv2d(4, width, 1)
        self.local = nn.ModuleList(
            [
                nn.Conv2d(
                    width,
                    width,
                    1 if kind == "fno" else 3,
                    padding=0 if kind == "fno" else 1,
                    padding_mode="circular",
                )
                for _ in range(2)
            ]
        )
        self.spectral = nn.ModuleList(
            [Spectral(width, modes) for _ in range(2)] if kind == "fno" else []
        )
        self.head = nn.Conv2d(width, 3, 1)

    def forward(self, x, f):
        f = f.reshape(-1, 1, 1, 1).expand(-1, 1, *x.shape[-2:])
        z = self.lift(torch.cat((x, f), dim=1))
        for i, local in enumerate(self.local):
            z = F.gelu(local(z) + (self.spectral[i](z) if self.spectral else 0))
        return x + self.head(z)


def normalize(x, m):
    import numpy as np

    return (x - np.asarray(m["mean"])[:, None, None]) / np.asarray(m["std"])[
        :, None, None
    ]


def denormalize(x, m):
    import numpy as np

    return (
        x * np.asarray(m["std"])[:, None, None] + np.asarray(m["mean"])[:, None, None]
    )
