# SFZの生成とリポジトリ構成

このドキュメントは、SFZファイルを再生成・変更する開発者向けです。演奏するだけであれば [README](../README.md) を参照してください。

## リポジトリ構成

| パス | 内容 |
| --- | --- |
| `SolfeSinger_010_*.sfz` / `SolfeSinger_011_*.sfz` | 各音源のsustain・decay・fold_sustain・fold_decayの4プリセット（計8 SFZ） |
| `samples/010/` / `samples/011/` | 各音源の66 WAVと `manifest.json` |
| `docs/registers.json` | 全プリセット・全鍵盤の割り当て（`utils/build_sfz.py` が生成） |
| `docs/REGISTERS.md` | 音域と鍵盤割り当ての解説 |
| `demos/` | 試聴ページと試聴WAV |
| `utils/build_sfz.py` | 8 SFZと `docs/registers.json` の生成スクリプト |
| `utils/audio_loudness.py` | 母音ラウドネスとトゥルーピークの計測 |

## SFZの生成

SFZと `docs/registers.json` は、各音源の `samples/*/manifest.json` とWAVから生成します。直接編集せず、manifestやスクリプトを変更して再生成してください。

```bash
python -m pip install -r utils/requirements.txt
python utils/build_sfz.py
```

`--check` を付けると、ファイルを書き換えずに生成結果との差分があるファイルを表示し、差分があれば終了コード1を返します。

```bash
python utils/build_sfz.py --check
```

### 割り当ての規則

- 全プリセットはMIDI 21–108を受け付け、鍵盤ごとに1リージョンを持ちます。
- 通常版は全鍵盤を要求どおりの音程で鳴らします（再生速度1/8〜4倍）。
- `_fold` 版は再生速度を0.5〜2倍に制限し、それを超える鍵盤は同じ階名の別オクターブへ1オクターブ単位で移します。
- 再生速度が1未満の鍵盤は `_r05.wav`、1を超える鍵盤は `_r2.wav` を使用します。
- 速度を変える鍵盤のリージョン音量は、再生後の母音ループのラウドネス（BS.1770）がmanifestの `normalization.vowel_lufs_target` に揃うように設定します。トゥルーピークが−1.01 dBTPを超える場合は、それを上限とします。

## manifest

`samples/*/manifest.json` には、各WAVの鍵盤・階名・目標周波数・フレーム数・ループ点・SHA-256（速度変更用WAVは元WAVと再生開始位置も）、音源全体の音量設定、使用した合成モデルを記載しています。`notes` が音程別WAV、`extension_samples` が速度変更用WAVです。

## 含まれないもの

TTSによる合成と、子音・母音の加工（PSOLA・WORLD）を行うパイプラインは含みません。WAVは完成済みのサンプルとして管理しています。

[使い方](../README.md) ／ [音域と鍵盤割り当て](REGISTERS.md) ／ [試聴](../demos/index.html)
