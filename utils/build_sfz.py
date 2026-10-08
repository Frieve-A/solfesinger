"""Build the SolfeSinger SFZ presets and docs/registers.json from the sample manifests.

Every preset accepts the 88 piano keys A0-C8 (MIDI 21-108). Each voice has
per-pitch WAVs for C3-F6 (MIDI 48-89); other keys play a WAV of the same
syllable at an octave-multiple playback rate.

* Regular presets keep the requested pitch on every key. Keys outside the
  sample range use playback rates from 1/8 to 4.
* Fold presets limit playback to 0.5, 1 or 2 times speed. Keys more than one
  octave outside the sample range sound in another octave of the same syllable.

Keys played at a rate other than 1 use the *_r05.wav (slower) or *_r2.wav
(faster) variants, whose consonant length and attack timing are pre-compensated
for half- and double-speed playback.

Usage: python utils/build_sfz.py [--check]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from audio_loudness import true_peak, vowel_loudness

ROOT = Path(__file__).resolve().parents[1]
VOICES = ('010', '011')
INPUT_LOW, INPUT_HIGH = 21, 108  # A0-C8
TRUE_PEAK_CEILING_DB = -1.01


def sample_key_for(output, low, high):
    """Nearest sample key of the same pitch class inside the sample range."""
    key = output
    while key < low:
        key += 12
    while key > high:
        key -= 12
    return key


def folded_output(key, low, high):
    """Fold by whole octaves until a same-class sample is within one octave."""
    while key < low - 12:
        key += 12
    while key > high + 12:
        key -= 12
    return key


class Voice:
    def __init__(self, number):
        self.number = number
        self.preset = f'SolfeSinger_{number}'
        self.manifest = json.loads((ROOT/'samples'/number/'manifest.json').read_text(encoding='utf-8'))
        self.notes = {n['key']: n for n in self.manifest['notes']}
        self.variants = {(n['key'], n['extension_playback_rate']): n
                         for n in self.manifest['extension_samples']}
        self.low, self.high = min(self.notes), max(self.notes)
        assert set(self.notes) == set(range(self.low, self.high + 1)), f'Incomplete sample set: {number}'
        self.target_lufs = self.manifest['normalization']['vowel_lufs_target']
        self.volume_db = self.manifest['normalization']['sfz_volume_db']
        self.gains = {}

    def note_for(self, sample_key, rate):
        if rate == 1:
            return self.notes[sample_key]
        return self.variants[sample_key, .5 if rate < 1 else 2]

    def gain_db(self, note, rate):
        """Region gain that matches the played vowel loudness, limited by true peak."""
        if rate == 1:
            return 0.
        cache_key = (note['sample'], rate)
        if cache_key not in self.gains:
            audio, sr = sf.read(ROOT/note['sample'])
            offset = note.get('playback_offset', 0)
            audio = audio[offset:]
            played = audio[::int(rate)] if rate >= 1 else resample_poly(audio, int(round(1/rate)), 1)
            a = round((note['loop_start'] - offset)/rate)
            b = round((note['loop_end'] + 1 - offset)/rate) - 1
            loudness = vowel_loudness(played, a, b, sr)
            peak = 20*np.log10(true_peak(played))
            self.gains[cache_key] = float(min(self.target_lufs - loudness, TRUE_PEAK_CEILING_DB - peak))
        return self.gains[cache_key]

    def region(self, key, fold):
        output = folded_output(key, self.low, self.high) if fold else key
        sample_key = sample_key_for(output, self.low, self.high)
        assert key % 12 == output % 12 == sample_key % 12
        rate = 2.**((output - sample_key)/12)
        note = self.note_for(sample_key, rate)
        return {
            'input_key': key, 'output_key': output, 'sample_key': sample_key,
            'sample': note['sample'], 'syllable': note['syllable'],
            'playback_rate': rate,
            # pitch_keycenter only sets the playback rate; it is not the WAV's own pitch.
            'sfz_pitch_keycenter': sample_key - (output - key),
            'region_volume_db': self.gain_db(note, rate),
            'playback_offset': note.get('playback_offset', 0),
            'loop_start': note['loop_start'], 'loop_end': note['loop_end'], 'frames': note['frames'],
        }


def sfz_text(voice, fold, mode, regions):
    if fold:
        title = f'{voice.number}_fold; max_one_octave; input MIDI 21-108; playback rates 0.5/1/2; compensated attack timing'
    else:
        title = f'{voice.number}; requested pitch; input MIDI 21-108; playback rates 1/8-4; compensated attack timing'
    lines = [f'// SolfeSinger {title}',
             '// Input/output/sample pitches and playback speeds: docs/registers.json',
             '<control>', 'hint_ram_based=1',
             '<global>', f'ampeg_attack=0.001 ampeg_release=0.14 amp_veltrack=70 volume={voice.volume_db}',
             'loop_mode=loop_sustain pitch_keytrack=100',
             'ampeg_decay=3.5 ampeg_sustain=0' if mode == 'decay' else 'ampeg_sustain=100']
    for r in regions:
        lines.extend(['<region>',
                      f"lokey={r['input_key']} hikey={r['input_key']} pitch_keycenter={r['sfz_pitch_keycenter']} sample={r['sample']}",
                      f"volume={r['region_volume_db']:.6f}",
                      f"offset={r['playback_offset']}",
                      f"loop_start={r['loop_start']} loop_end={r['loop_end']} end={r['frames']-1}"])
    return '\n'.join(lines) + '\n'


def build():
    outputs, instruments, voices = {}, [], []
    for number in VOICES:
        voice = Voice(number)
        generation = voice.manifest['generation']
        voices.append({'preset': voice.preset, 'engine': generation['engine'], 'speaker': generation['voice'],
                       'sample_key_range': [voice.low, voice.high]})
        for fold in (False, True):
            name = voice.preset + ('_fold' if fold else '')
            regions = [voice.region(key, fold) for key in range(INPUT_LOW, INPUT_HIGH + 1)]
            for mode in ('sustain', 'decay'):
                outputs[f'{name}_{mode}.sfz'] = sfz_text(voice, fold, mode, regions)
            instruments.append({
                'preset': name,
                'range_policy': 'max_one_octave' if fold else 'requested_pitch',
                'input_key_range': [INPUT_LOW, INPUT_HIGH],
                'output_key_range': [min(r['output_key'] for r in regions), max(r['output_key'] for r in regions)],
                'playback_rates': sorted({r['playback_rate'] for r in regions}),
                'regions': regions})
    document = {
        'version': 5,
        'pitch_reference': 'MIDI 69=A4=440 Hz; C4=MIDI 60',
        'sfz_mapping': 'Each key has its own region (lokey=hikey=input_key). sample_key is the pitch of the WAV; '
                       'sfz_pitch_keycenter is input_key minus the octave shift and only sets the playback rate.',
        'range_policy': 'All presets accept A0-C8 / MIDI 21-108; per-pitch samples cover C3-F6 / MIDI 48-89. '
                        'Regular presets keep the requested pitch on every key (playback rates 1/8-4). '
                        'Fold presets keep playback rates within 0.5-2 and fold more distant keys by whole octaves.',
        'voices': voices,
        'instruments': instruments,
    }
    outputs['docs/registers.json'] = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='report differences without writing files')
    args = parser.parse_args()
    outputs = build()
    changed = [name for name, text in outputs.items()
               if not (ROOT/name).exists() or (ROOT/name).read_bytes() != text.encode('utf-8')]
    if args.check:
        print('\n'.join(changed) if changed else 'All SFZ files and docs/registers.json are up to date.')
        sys.exit(1 if changed else 0)
    for name in changed:
        (ROOT/name).write_bytes(outputs[name].encode('utf-8'))
    print(f'Wrote {len(changed)} of {len(outputs)} files.')


if __name__ == '__main__':
    main()
