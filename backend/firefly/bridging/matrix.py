"""
橋接計分:矩陣分解 / Bridging score: matrix factorization(文件 05;基底為 Community Notes 公開實作,裁剪至本專案規模)。

模型 / Model:  r_{u,c} ≈ μ + i_u + i_c + f_u · f_c
損失 / Loss:   Σ w_{u,c} (r − pred)² + λ_i (Σ i_u² + Σ i_c²) + λ_f (Σ‖f_u‖² + Σ‖f_c‖²)

以交替最小平方(ALS)求解:固定使用者參數解每張卡的小型 ridge 迴歸,再反之。純 numpy,單機分鐘級。
Solved by alternating least squares: with user params fixed each card is a small ridge regression, then vice versa.

D-013:θ_helpful 只在搭配 λ_i、λ_f 時有意義;三者同在 config/firefly.yaml。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Rating:
    u: int  # 使用者索引 / user index
    c: int  # 卡片索引 / card index
    r: float  # 1 有幫助 / 0 沒幫助
    w: float = 1.0  # 權重(降權後 < 1)/ weight


@dataclass
class FactorizationResult:
    mu: float
    i_u: np.ndarray
    i_c: np.ndarray
    f_u: np.ndarray  # shape (n_users, dim)
    f_c: np.ndarray  # shape (n_cards, dim)
    iterations: int
    loss: float


def factorize(ratings: list[Rating], n_users: int, n_cards: int, dim: int = 1, lambda_intercept: float = 0.15, lambda_factor: float = 0.03, iterations: int = 40, seed: int = 0, tol: float = 1e-6) -> FactorizationResult:
    rng = np.random.default_rng(seed)
    R = np.array([[x.u, x.c, x.r, x.w] for x in ratings], dtype=float) if ratings else np.zeros((0, 4))
    if len(R) == 0:
        return FactorizationResult(0.0, np.zeros(n_users), np.zeros(n_cards), np.zeros((n_users, dim)), np.zeros((n_cards, dim)), 0, 0.0)
    U, C, Y, W = R[:, 0].astype(int), R[:, 1].astype(int), R[:, 2], R[:, 3]
    mu = float(np.average(Y, weights=W))
    i_u, i_c = np.zeros(n_users), np.zeros(n_cards)
    f_u, f_c = rng.normal(0, 0.1, (n_users, dim)), rng.normal(0, 0.1, (n_cards, dim))
    lam = np.diag(np.concatenate([[lambda_intercept], np.full(dim, lambda_factor)]))

    def solve_side(idx_all: np.ndarray, n: int, other_i: np.ndarray, other_f: np.ndarray, other_idx: np.ndarray, out_i: np.ndarray, out_f: np.ndarray) -> None:
        # 每個實體:最小化 Σ w (y − μ − i_other − i_self − f_other·f_self)² + 正則化 / per-entity ridge
        order = np.argsort(idx_all, kind="stable")
        s_idx, s_other, s_y, s_w = idx_all[order], other_idx[order], Y[order], W[order]
        starts = np.searchsorted(s_idx, np.arange(n + 1))
        for e in range(n):
            a, b = starts[e], starts[e + 1]
            if a == b:
                out_i[e] = 0.0
                out_f[e] = 0.0
                continue
            o = s_other[a:b]
            X = np.column_stack([np.ones(b - a), other_f[o]])  # [1, f_other]
            y = s_y[a:b] - mu - other_i[o]
            w = s_w[a:b]
            A = X.T @ (X * w[:, None]) + lam
            beta = np.linalg.solve(A, X.T @ (w * y))
            out_i[e] = beta[0]
            out_f[e] = beta[1:]

    prev = np.inf
    it = 0
    while it < iterations:
        it += 1
        solve_side(C, n_cards, i_u, f_u, U, i_c, f_c)
        solve_side(U, n_users, i_c, f_c, C, i_u, f_u)
        pred = mu + i_u[U] + i_c[C] + np.sum(f_u[U] * f_c[C], axis=1)
        loss = float(np.sum(W * (Y - pred) ** 2) + lambda_intercept * (np.sum(i_u**2) + np.sum(i_c**2)) + lambda_factor * (np.sum(f_u**2) + np.sum(f_c**2)))
        if abs(prev - loss) < tol:
            break
        prev = loss
    return FactorizationResult(mu, i_u, i_c, f_u, f_c, it, prev if np.isfinite(prev) else 0.0)


def spectrum_coverage(rater_factors: np.ndarray, min_raters: int) -> float | None:
    """光譜多元度:投票者立場向量(第一維)雙峰覆蓋度 = 2·min(p₋, p₊) ∈ [0,1]。投票者不足回 None。
    Bimodal coverage of raters' first-factor signs; None when too few raters."""
    if rater_factors is None or len(rater_factors) < min_raters:
        return None
    signs = np.sign(rater_factors[:, 0])
    n_pos, n_neg = int(np.sum(signs > 0)), int(np.sum(signs < 0))
    total = n_pos + n_neg
    if total == 0:
        return 0.0
    return round(2 * min(n_pos, n_neg) / total, 4)


def burst_zscore(counts_per_window: list[int]) -> float:
    """最近一個時窗的投票數相對歷史時窗的 z-score(文件 05 突發灌票偵測)。/ z-score of the latest window vs history."""
    if len(counts_per_window) < 3:
        return 0.0
    hist = np.array(counts_per_window[:-1], dtype=float)
    sd = hist.std() or 1.0
    return float((counts_per_window[-1] - hist.mean()) / sd)
