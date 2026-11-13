# Helper CLI

The helper requires Python 3.9+ and Pillow:

```bash
python -m pip install Pillow
```

## Analyze a batch

```bash
python scripts/sprite_extract.py analyze \
  --input extracted/screenshots \
  --roi 420,20,700,130 \
  --background black \
  --threshold 4 \
  --padding 10 \
  --report analysis.json \
  --contact-sheet contact-sheet.png
```

`--roi` is `x,y,width,height`. The report includes per-image bounds, their foreground union, and the recommended padded crop.

Background choices for analysis:

- `black`: foreground differs from black.
- `white`: foreground differs from white.
- `alpha`: foreground is determined by the existing Alpha channel.
- `color`: use `--bg-color RRGGBB`.

## Extract and remove the background

```bash
python scripts/sprite_extract.py extract \
  --input extracted/screenshots \
  --output outputs/transparent \
  --crop 536,59,400,73 \
  --background black-to-alpha-white \
  --threshold 2 \
  --names-csv names.csv \
  --zip outputs/transparent.zip
```

Extraction background choices:

- `keep`: retain source pixels.
- `black-to-alpha-white`: rebuild white antialiased artwork from a black background.
- `black-to-alpha-preserve`: preserve colored artwork while estimating Alpha from a black background.
- `color-to-alpha`: remove `--bg-color` using color distance.

`names.csv` is optional and must contain `source,output`. Extra columns are copied into the generated manifest.

## Validate existing outputs

```bash
python scripts/sprite_extract.py validate \
  --input outputs/transparent \
  --expected-count 90 \
  --expected-size 400,73 \
  --require-transparent-corners
```

The command exits nonzero when validation fails.

