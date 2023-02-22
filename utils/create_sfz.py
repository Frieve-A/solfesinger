import soundfile as sf
import numpy as np
import argparse
import os

def func(args):
    # Open input wav file
    name = os.path.splitext(os.path.basename(args.input_wav))[0]
    data = sf.read(args.input_wav)[0]

    # Detect waveform onsets
    count = 0
    pos_list = []
    for pos, sample in enumerate(data):
        if abs(sample[0]) > args.threshold_signal:
            if count < 0:
                pos_list.append(pos)
            count = 10000
        elif abs(sample[0]) < args.threshold_silence:
            count -= 1

    print(f'{len(pos_list)} sounds are detected. Onsets : {pos_list}')
    assert len(pos_list) == 37, '37 sounds from C3 to C6 could not be detected. Check if the input waveform correctly contains these 37 sounds in order, and adjust the t1 and t2 options as necessary.'

    # Prepare regions
    regions = []
    for i, pos in enumerate(pos_list):
        key = 48 + i
        if args.individual_onset_detection:
            offset = pos_list[i]
            end = pos_list[i + 1] if i + 1 < len(pos_list) else len(data)
        else:
            offset = int((pos_list[12] - pos_list[0]) / 12 * i + pos_list[0])
            end = offset + pos_list[1] - pos_list[0]
        max_val = np.max(abs(data[offset:end]))
        volume = np.log(max_val) / np.log(2) * -6.0

        base_str =  f'pitch_keycenter={key}\n offset={offset} end={end}\n'
        regions.append([key, f' lokey={key} hikey={key} ' + base_str, volume])

        if i < 12:
            for j in range(2):
                key2 = 48 + i - (j + 1) * 12
                regions.append([key2, f' lokey={key2} hikey={key2} ' + base_str, volume])

        if i > 24:
            for j in range(2):
                key2 = 48 + i + (j + 1) * 12
                regions.append([key2, f' lokey={key2} hikey={key2} ' + base_str, volume])
    
    regions.sort(key=lambda v:v[0])

    # Output sfz files
    with open(f'{name}_sustain.sfz', 'wt') as w:
        w.write('<global>\n')
        w.write(f' sample={name}.wav\n')

        for region in regions:
            w.write('<region>\n')
            w.write(region[1] + f' volume={region[2] - 3.0}\n')

    with open(f'{name}_decay.sfz', 'wt') as w:
        w.write('<global>\n')
        w.write(f' sample={name}.wav\n')
        w.write(f' ampeg_decay=8 ampeg_sustain=10\n')

        for region in regions:
            w.write('<region>\n')
            w.write(region[1] + f' volume={region[2]}\n')

    print('Sfz files created successfully.')


def main():
    parser = argparse.ArgumentParser(
        description='Create sfz file from wav file with long tone from C3 to C6 in order.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        '-i',
        '--input_wav',
        help='Input wav file name',
        required=True)
    parser.add_argument(
        '-t1',
        '--threshold_signal',
        help='threshold for singing voice detection between 0.0 and 1.0. Set a larger value if the input is an acoustic recording that contains noise. default=0.0001',
        type=float,
        default=0.0001)
    parser.add_argument(
        '-t2',
        '--threshold_silence',
        help='threshold for silence detection between 0.0 and 1.0. Set a larger value if the input is an acoustic recording that contains noise. default=0.00005',
        type=float,
        default=0.00005)
    parser.add_argument(
        '-o',
        '--individual_onset_detection',
        help='Specify when using notes that are not the same in length and timing.',
        action='store_true')

    parser.set_defaults(func=func)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()