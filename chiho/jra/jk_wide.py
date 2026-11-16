"""ワイドの組の見込み（検証計画「ワイドの研究」WD3）。組（i, j）が両方とも3着内に来る見込みを、1着の見込みから
「強さの順に1頭ずつ決まる」形（ハービル型。2着は強さを λ2 乗、3着は λ3 乗して弱める）で全部の3頭の並びを足して出し、単調な直しをかける。
直しの表：中央 jra_wide_calib.json・地方 an/wide_calib.json（λ2・λ3 は2021〜2023年で決め、直しも2021〜2023年。2024〜2026年で合い方を確かめた。wd3.py）。"""
import numpy as np


def pairprob(p, l2, l3):
    """p：1着の見込み（足して1）。返すのは n×n の表（i, j が両方3着内に来る見込み。直す前）"""
    p = np.clip(np.asarray(p, dtype=float), 1e-5, 1); n = len(p); q = p ** l2; r = p ** l3; Q = q.sum(); R = r.sum()
    A = p[:, None] * q[None, :] / (Q - q[:, None]); np.fill_diagonal(A, 0)
    den = R - r[:, None] - r[None, :]; np.fill_diagonal(den, 1)
    T = A[:, :, None] * r[None, None, :] / den[:, :, None]
    idx = np.arange(n); T[idx, :, idx] = 0; T[:, idx, idx] = 0
    M = T.sum(2) + T.sum(1) + T.sum(0)
    return M + M.T


def top_wide(nums, p1, CAL, m=3):
    """見込みの高い順に m 組：[('馬番-馬番', 見込み), …]。4頭より少ないレースは出さない"""
    nums = np.asarray(nums).astype(int); p1 = np.asarray(p1, dtype=float); p1 = p1 / p1.sum()
    if len(nums) < 4: return []
    M = pairprob(p1, CAL['λ2'], CAL['λ3']); iu = np.triu_indices(len(nums), 1)
    v = np.interp(M[iu], CAL['見込み'], CAL['直した見込み']); o = np.argsort(-M[iu], kind='stable')[:m]
    return [('-'.join(str(x) for x in sorted((nums[iu[0][k]], nums[iu[1][k]]))), float(v[k])) for k in o]
