# aviutl2-catalog-authors-plot

AviUtl2カタログの作者ごとの登録数ランキング

## Usage

```sh
uv run main.py --type プラグイン,スクリプト
```

`--type` filters catalog items by their `type`. Multiple types can be separated by commas.
`プラグイン` is treated as `MOD` or `*プラグイン`.

Authors get stable colors from a hash-derived hue. Put overrides in `author_color_overrides.json` in the
current working directory to replace specific authors or `Others`:

```json
{
  "作者名": "#ff0000",
  "Others": "#666666"
}
```
