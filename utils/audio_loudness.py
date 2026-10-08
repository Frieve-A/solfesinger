"""Steady-vowel K-weighted loudness and 4x oversampled true-peak checks."""
import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly


def vowel_loudness(wav, loop_start, loop_end, sample_rate):
    return float(pyln.Meter(sample_rate).integrated_loudness(np.tile(wav[loop_start:loop_end+1],4)))


def true_peak(wav):
    return float(np.max(np.abs(resample_poly(wav,4,1))))
