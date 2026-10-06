# tools/ — 公開文件產線

原稿只在 `DocSources/<App>/<Doc>_<lang>.md`（`AboutMe`、`PrivacyPolicy`、`TermsOfUse` × `zh`、`ja`、`en`）；
HTML 一律由腳本產生，不手改。模板在 `DocSources/_template/`（`page.html` + `style.css`，CSS 會內嵌進每一頁）。

## 用法

```
python3 tools/build_docs.py --app LIV --date 250529            # DocSources/LIV/ → Stage/LIV250529/
python3 tools/build_docs.py --app LIV --date 250529 --check    # 只比對 Stage 現有 HTML 的去標籤文字，不寫檔
python3 tools/build_docs.py --app QCC --date 210917            # 檔名表在腳本頂端 APPS，每 App 不同（QCC 隱私權單檔、條款日期 211011）
```

需求：Python 3.11 + `markdown` 套件（已裝 3.6）。不裝 pandoc、不引入產生器。

## 提醒

- **腳本只寫 `Stage/`，永遠不碰 `Release/`，也不碰任何 `version-info.json`。**
  `Stage/` 用 debug build 驗過之後，再**手動**把 HTML 複製到 `Release/<App><yymmdd>/`（P3）；
  `version-info.json` 要不要動是每次上架另外決定的事（D16）。
- 產出檔名是 App 程式碼寫死的（P1），只加不改；新 App 在 `APPS` 表加一列就好。
- 原稿寫法：一行一段，段落間空一行；換行就是換行（腳本開了 `nl2br`），
  所以「Robin Hsu⏎E-Mail: …」、「1. …⏎2. …」會各自一行。清單前面要空一行才會變成清單。
