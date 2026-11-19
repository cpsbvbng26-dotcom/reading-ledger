# reading-ledger

[English](./README.en.md)

論文ごとに、引いた文献をどこまで読んだか、どの版を読んだか、いつ読んだかを残す台帳です。
引いたことと読んだことは別のことです。
この台帳は、その差を項目ごとに書いておくためにあります。
保存版は Zenodo にあります。
最初の版の DOI は [`10.5281/zenodo.24382375`](https://doi.org/10.5281/zenodo.24382375) です。
すべての版に共通する DOI は [`10.5281/zenodo.24382374`](https://doi.org/10.5281/zenodo.24382374) です。

## 台帳

台帳は `ledger/` に、作品ごとに TOML で置いてあります。
台帳は 4 本です。
項目は合わせて 93 件です。

| 台帳 | 作品 | 読み方の記録の出どころ |
| --- | --- | --- |
| `golden-window-resolution.toml` | golden-window-resolution の稿（`paper/golden-window-resolution.tex`） | 稿の節 Literature, and how each item was read と文献の欄 |
| `joint-continuity.toml` | 同じリポジトリの続きの稿（`continuity/paper/joint-continuity.tex`） | 稿の同じ名の節と、`continuity/REFEREE.md` |
| `trinity-operator-games.toml` | trinity-operator の `games/README.md` | 節 The literature check of 2026-11-18 の Sources of the check |
| `lit-check-2026-11-18.toml` | 2026-11-18 の文献の確認の控え（`sources/lit-check-2026-11-18.md`） | 控えそのもの |

最後の台帳は、作品ではなく検索の控えです。
控えに挙がった文献は、どこにも引かれていなくても項目になります。

## 項目の欄

| 欄 | 中身 |
| --- | --- |
| `key` | 稿の `\bibitem` の鍵。Markdown の作品では DOI。控えでは名と年 |
| `citation` | 紙面に印字されたとおりの書誌 |
| `title`・`first_author` | 書誌の題と、筆頭の著者の姓 |
| `doi` | 紙面が印字した DOI |
| `doi_found`・`doi_found_title` | 紙面は印字していないが、登録の記録で見つかった DOI と、その題 |
| `arxiv`・`arxiv_version`・`arxiv_title` | 読んだ arXiv の番号と版と、その版の題 |
| `arxiv_from` | 紙面が arXiv の番号か版を書いていないときに、読んだ版が分かった所 |
| `reading` | 読み方。下の表のどれか |
| `sections` | 読んだ節 |
| `quoted_in` | 読まずに、他人の文献の挙げ方で引いたときの、その文献 |
| `date_read`・`date_read_until` | 読んだ日。日を絞れないときは、前と後ろの日で挟む |
| `cited_in` | 引いたファイル |
| `evidence` | 読み方の出どころ |
| `relied_on`・`see` | その文献に何を頼ったか。関係する訂正の記録 |
| `note` | 注。紙面の題と登録の記録の題の違いなど |

| `reading` | 意味 |
| --- | --- |
| `read` | 本文を読んだ。`sections` に読んだ節がある |
| `abstract only` | 要旨だけを読んだ |
| `record only` | 書誌の記録だけを見た。要旨も本文も読んでいない |
| `not read; cited as quoted in` | 読んでいない。`quoted_in` の文献の挙げ方で引いた |
| `recalled, not read` | 記憶から挙げた。読んでいない |
| `own work` | 著者自身の稿や記録 |
| `not stated` | 出どころが、読み方を書いていない |

## 検査

検査は、登録の記録、作品が印字したもの、控えの順に突き合わせます。
最初は、登録の記録です。
DOI は Crossref で引き、Crossref に無ければ DataCite で引きます。
arXiv の番号は、版ごとに arXiv の API で引きます。
題と筆頭の著者が台帳と合わなければ、検査が落ちます。
次は、作品が印字したものです。
稿の `\bibitem` のどれにも項目があり、どの項目も `\bibitem` に当たるかを見ます。
印字された DOI・arXiv の番号・読んだ版・読み方の分類が、台帳と同じかも見ます。
最後は、控えです。
控えに出てくる DOI と台帳の DOI が、過不足なく同じかを見ます。

```
python3 verification/check.py            # 台帳を、控えた登録の記録と作品の写しと突き合わせる（外へ出ない）
python3 verification/check.py --online   # 登録の記録と作品を取り寄せ直して突き合わせる
python3 verification/check.py --record   # 取り寄せ直し、verification/cache/ に書く
python3 verification/check.py --break    # 検査を一つずつ壊し、落ちることを確かめる
```

CI は、外へ出ない検査を push と PR のたびに回します。
取り寄せ直す検査は、別の仕事として同じときと週に一度回します。
作品の側の稿が変われば、記したコミットの値を上げて取り寄せ直します。

## 例：Raith の論文

golden-window-resolution の稿は、`Corollary 7.2` の証明で、Allaart・Kong の `Lemma 6.2` の出どころを Raith の 1989 年の論文としました。
Allaart・Kong 自身が挙げているのは、Raith の 1994 年の論文です。
稿はどちらの論文も読んでいません。
2026-11-19 に続きの稿を査読したとき、この食い違いが見つかりました。
self-correction の GW-001 が、この訂正を記録しています。
公開した PDF は凍結しており、直していません。

台帳では、それぞれの稿がどの Raith の論文に頼ったかを、項目ごとに書いています。
`golden-window-resolution.toml` の `Raith89` は、`recalled, not read` です。
`joint-continuity.toml` の `Raith94` は、`not read; cited as quoted in` で、Kalle・Kong・Langeveld・Li と Allaart・Kong の挙げ方で引いています。
両方の項目が `see` に GW-001 を持ち、検査がその組を見ます。
控えの台帳の `raith-1989` は、2026-11-18 の確認がこの論文を次元の公式の出どころと推し量ったことを残しています。

## 見つけたこと

台帳を登録の記録と突き合わせたとき、紙面の題と読んだ版の題が違う文献が見つかりました。

- Barnsley・Steiner・Vince の項目は、雑誌の版の題を印字しています。
- 読んだ arXiv の版の題は、別の題でした。
- その雑誌の版の DOI は、紙面に印字されていません。
- Crossref が返した DOI を、`doi_found` に置きました。
- Sun・Li の項目では、arXiv の題と雑誌の題の結びが違います。

## 探して、台帳に入れなかったもの

autonomy-and-self-cultivation の `verification/references.toml` は、哲学の論文の典拠を並べています。
その台帳は、読んだかどうかの欄を、わざと置いていません。
内面は外から確かめられない、という理由が書いてあります。
読み方の記録が無いので、ここには写していません。
trinity-infinity の `ERRATA.md` の E8 は、Friedkin・Johnsen の原典に当たっていないと書いています。
Trinity-Infinity の紙面は、その文献を引いていません。
そのため、E8 の記録は golden-window-resolution の台帳の `FJ90` の注にだけ書きました。

## 運営者

運営者は、根本卓哉（Takuya Nemoto）です。
ORCID iD は [0009-0000-1406-0547](https://orcid.org/0009-0000-1406-0547) です。
誤りは[誤りの知らせ](https://github.com/cpsbvbng26-dotcom/reading-ledger/issues/new?template=error-report.yml)の様式で受けます。
安全の問題は、[SECURITY.md](./SECURITY.md) の入口で受けます。

## 言語モデルの使い方

台帳と検査は、運営者が求め、Claude Code（Anthropic）が書きました。
台帳の読み方は、作品と控えに書かれた読み方を写したものです。
台帳を作るときに、文献を読み直してはいません。
控え（`sources/lit-check-2026-11-18.md`）は、2026-11-18 に運営者が求め、Claude Code（Anthropic）が文献を検索して書いた報告です。
控えは言語モデルを使った確認で、人が文献を読んだ記録ではありません。
控えの中で書き手が自分を指す語（my own check の my など）は、その報告を書いた Claude Code を指します。
控えは、手を加えずに置いています。
Claude は著者ではありません。

## ライセンス

台帳と文は [CC BY 4.0](./LICENSE)、コードは [MIT](./LICENSE-CODE) です。
控えた登録の記録の題と著者名は、それぞれの登録の場の記録です。
控え（`sources/lit-check-2026-11-18.md`）は、引用符で囲んだ短い文を含みます。
多くは、控えが挙げる文献の要旨からの引用です。
引いた文は CC BY 4.0 でも MIT でも許諾しておらず、それぞれの権利者のものです。
