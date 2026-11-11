<p align="right"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <strong>日本語</strong> · <a href="README.es.md">Español</a></p>

# Ruin Everything

### ブラウザーはエージェントに。時間はあなたに。

**クリックのたびに、付き添わなくていい。**

Ruin Everything は、**ブラウザーエージェントのためのローカル Chrome ランタイム**です。共有 Chrome プロファイルのログイン状態、Cookie、拡張機能を使い、バックグラウンドでページを開き、フォームに入力し、内容を読み取ります。対応するログインや認証の手順を進め、何が完了したかを確認できる結果を返します。

<img src="docs/figures/core-workflow.svg" alt="A：エージェントが Ruin 経由で共有 Chrome の背景タブを操作。B：ローカルログインと対応する認証を利用。C：サイトの確認を証拠とし、Ashby の受付記録を保存。" width="100%">

<p align="center">
  <a href="https://github.com/yuki4266/ruin-everything/stargazers"><img src="docs/figures/badges/stars.svg" alt="GitHub スター"></a>
  <a href="#quickstart"><img src="docs/figures/badges/python.svg" alt="Python 3.11 以上"></a>
  <a href="#connect-an-agent-over-mcp"><img src="docs/figures/badges/mcp.svg" alt="stdio による MCP"></a>
  <a href="LICENSE"><img src="docs/figures/badges/license.svg" alt="MIT ライセンス"></a>
</p>

[始める](#quickstart) · [主な機能](#core-features) · [利用例](#real-workflows) · [検証状況](#verification) · [技術リファレンス（英語）](docs/runtime-reference.md)

## 見張る時間を減らして、作業を先へ。

ページを開くとログイン。入力が終わるとメールのコード。送信すると画像認証。そして会話が終わる頃には、応募できたのかも分からない。

**Ruin は、作業を何度も止めるブラウザーの手順を引き受けます。** 図 A は共有ブラウザー、B はログインと認証、C は後から確認できる結果です。

<a id="core-features"></a>

| 主な機能 | できること |
| --- | --- |
| **いつもの状態から続ける** | サイトを移動し、クリック、入力、選択、テキスト取得を実行。エージェントの接続が変わっても同じプロファイル、Cookie、拡張機能を利用。 |
| **裏で動く。あなたの作業を続けられる。** | 操作可能なタブをバックグラウンドに作成。前面アプリを切り替えず、無関係なタブを保持。 |
| **ログインを再利用** | 手動のパスワードログインをローカルに記録し、対応するフォームで再利用。Cookie と Web Storage のバックアップで再起動後の復元を支援。有効期限はサイトが決定。 |
| **対応する認証をその場で処理** | 元のタブで新着メールコード、SMS コード、画像パズルを扱う。未解決なら保留状態を返す。 |
| **アカウント設定の繰り返しを減らす** | ローカルの本人情報で対応する登録・連絡先フォームに入力。任意の Workday/iCIMS 復旧で既知のエラーとパスワード再設定を処理。 |
| **応募の証拠を残す** | Ashby の公式な送信確認を求人 URL ごとに保存。Chrome を閉じた後でも保存済みの受付記録を確認。 |

一般的なブラウザー操作の入口は `ruin_browser`。以下のサイトは追加対応の例です。エージェントが作業を計画し、Ruin がブラウザー操作を実行します。

<a id="quickstart"></a>
<a id="use-a-shared-local-chrome-window"></a>

## 3 ステップで始める

<img src="docs/figures/local-chrome.svg" alt="別々のエージェント接続が同じローカル Chrome プロファイルと元のタブを共有。" width="100%">

### 1. 共有ブラウザーを起動

**Python 3.11+、Google Chrome、[uv](https://docs.astral.sh/uv/getting-started/installation/)** を用意します。ここでは、紹介する機能を含む現在の GitHub コードを使います。

```sh
uvx --from 'ruin-everything @ git+https://github.com/yuki4266/ruin-everything.git@main' ruin browser
```

`127.0.0.1:9222` の Chrome を起動または再接続します。永続プロファイルは `~/.ruin-everything/canvas-browser`。必要なサイトには**このプロファイルで**ログインしてください。別の Chrome プロファイルからログインを取り込む機能ではありません。コマンド終了後も Chrome とタブは開いたままです。

<a id="connect-an-agent-over-mcp"></a>

### 2. エージェントを接続

MCP クライアントの設定に追加し、接続を再起動します。クライアントから `uvx` を実行できる必要があります。

```json
{
  "mcpServers": {
    "ruin-everything": {
      "command": "uvx",
      "args": [
        "--isolated", "--refresh", "--from",
        "ruin-everything @ git+https://github.com/yuki4266/ruin-everything.git@main",
        "ruin-mcp"
      ],
      "env": { "RUIN_AUTO_UPDATE": "0" }
    }
  }
}
```

公開済みパッケージを使う場合は Git の指定を `ruin-everything` に変更します。Git の更新は次回のサーバー起動時に反映されます。PyPI の機能は公開バージョンによります。[インストールと更新の詳細](docs/runtime-reference.md#how-updates-reach-your-machine)。

<a id="first-mcp-call"></a>

### 3. 作業を頼む

> Use Ruin to open https://example.org and tell me the page title and visible links.

入口は `ruin_browser(operation="navigate", url="https://example.org")`。以降は返された現在の URL を使います。MCP サーバー自体に API キーは不要で、エージェント自身のモデル接続を利用します。任意の独立したモデル駆動 CLI には agent 追加依存と `OPENAI_API_KEY` が必要です。

登録・アカウント機能は、永続的にインストールしたチェックアウトで `ruin identity` を実行して設定します。背景に開いた編集タブを選び、本人情報と自動登録の有効・無効を設定してください。`ruin ats-setup` は ATS パスワード復旧を別途有効にします。[設定方法](docs/runtime-reference.md#local-account-registration)。

<a id="real-workflows"></a>
<a id="institutional-sign-in-in-the-background"></a>

## 役立つ場面と、確認できたこと

<img src="docs/figures/post-action.svg" alt="元のタブで送信後の画像認証を確認し、対応する処理を試行。送信完了はサイトの受付表示で確認。" width="100%">

| やりたいこと | Ruin の追加機能 | 検証状況 |
| --- | --- | --- |
| **採用サイトの画像認証を進める** | ZhongAn/Moka の対応ジグソー、Feishu Jobs の回転スライダーを処理。 | 両方で実サイトの SMS 再送カウントダウンを確認。ZhongAn では成功ページと応募履歴も確認。 |
| **Greenhouse のメール認証を完了する** | 雇用主とリクエストに合う新着 Outlook メールを選び、元の求人タブへコード入力。 | ブラウザーの模擬テスト。実際の雇用主・Outlook テナントとの互換性は未検証。 |
| **Workday / iCIMS アカウントを復旧する** | ローカル情報、対応する登録・有効化、任意の回数制限付きパスワード復旧。 | ブラウザーの模擬テストと実 Workday ダイアログの確認。テナントにより画面が異なる。 |
| **Ashby の応募結果を確認する** | 公式の確認を待ち、求人 URL ごとに受付記録を保存。 | ローカル記録・ブラウザー統合テスト。記録がなければ結果は不明。 |
| **Duke の機関アクセスで論文を読む** | IEEE、ACM、Springer の対応フローと、入力済み Duke ログイン、Duo の端末信頼を続行。 | IEEE 検索、Duke への移動、PDF アクセスを実測。ACM / Springer は模擬テスト。 |

対応は特定のフローが対象です。一部の画像認証にはローカル Ollama 視覚モデル、SMS には macOS Messages の読み取り権限、メール処理には Outlook Web のログインが必要です。スマートフォンでの承認や未対応の確認は手動操作が必要な場合があります。[前提条件とコマンド](docs/runtime-reference.md)。

承認済みのフォーム送信には `ruin_action` を使い、正確な現在の URL と表示されたボタン名を指定します。クリック後に認証を確認します。**認証の通過は途中経過。送信の証拠はサイトの受付表示です。**

## 6 つのツール、1 つの共有ブラウザー

<img src="docs/figures/challenge-routing.svg" alt="正確な求人 URL で認証の種類を判定し、元の応募フォームを保持。" width="100%">

| ツール | 用途 |
| --- | --- |
| `ruin_browser` | タブ一覧、移動、確認、読み取り、クリック、入力、キー操作、選択。 |
| `ruin_action` | 承認済み送信と対応する後続認証。ボタンを省略すると再開。 |
| `ruin_auto_register` | 本人情報を使って対応する登録、アカウント、SMS ログインを続行。 |
| `inspect_application_challenge` | Greenhouse / Ashby の認証を特定、または対応する応募タブを探す。 |
| `get_ashby_receipt` | Chrome を開かずに保存済み受付記録を確認。 |
| `watch_ashby_receipt` | 元の Ashby タブで確認を待ち、記録を保存。 |

[エージェント用ルール](AGENTS.md) · [CLI と詳細](docs/runtime-reference.md) · [信頼済みログイン設定](docs/trusted-auth.md)

## ブラウザーもログイン情報も、手元に。

<img src="docs/figures/local-auth-vault.svg" alt="手動ログインを所有者のみ読み書きできるローカルファイルに保存。対応するログインを実行し、Cookie と Web Storage を次のセッションで復元。" width="100%">

ブラウザー操作と認証情報の処理はローカルで動きます。**自動ログイン用の保管庫は平文パスワードを保存します。** 保存先は `~/.ruin/auth_vault.json`、権限は所有者のみ読み書きできる `0600`。パスワードはエージェントのツール結果に含まれません。Cookie と Web Storage もローカルにバックアップします。`RUIN_LOCAL_AUTH_VAULT=0` で、そのクライアントからのリスナー自動起動を無効にできます。[保存範囲と動作](docs/runtime-reference.md#local-auth-vault)。

接続したエージェントがページの文字をモデル提供者に送る場合はあります。サイトのセッションは失効し、一部の認証には人の操作が必要です。Ruin は状態を保持して対応する手順を再開しますが、永久ログインや全サイトでの成功は保証しません。

<a id="verification"></a>

## 検証の範囲を確認する

<img src="docs/figures/checks.svg" alt="ローカルブラウザーテストでランタイムを検証し、実サイトの観察は別に記録。" width="100%">

**今回の検証：ローカル回帰テスト 103 件、ソース配布物と wheel のビルド、Twine の厳格なメタデータ検査がすべて成功しました。** 初回成功、2 回目・3 回目の復旧、連続失敗の各分岐も確認済みです。実サイトの手順は再実行していません。

<img src="docs/figures/build-retry.svg" alt="Chromium の導入は最大 3 回。失敗が続くとビルドを停止し、テストと配布物の検査に成功した場合のみ公開します。" width="100%">

直近の CI 失敗は Chromium の依存関係を導入する際の Ubuntu ミラーの名前解決エラーでした。導入は最大 3 回試行し、再試行前に 15 秒、30 秒待機します。ステップ全体の制限は 30 分です（図 A–B）。テストと配布物の検査が成功してから PyPI に公開します（C）。失敗が続く場合は公開せず、既存のリリースは変わりません。[CI 結果](https://github.com/yuki4266/ruin-everything/actions/workflows/publish.yml)。

ローカルテストは共有セッション、背景タブ、ログイン記録と復元、テナント境界、認証の振り分け、受付記録を対象にしています。上表で実サイトの観察と模擬テストを分けています。各条件と制約はリファレンスをご覧ください。

開発チェックアウトでの回帰テスト：

```sh
python -m pip install -e '.[agent]'
python -m playwright install chromium
RUIN_AUTO_UPDATE=0 RUIN_RULE_UPDATES=0 python -m unittest discover -s tests -v
```

図は Rough.js と Kalam を使ったオリジナルの編集可能 SVG です。[図のソース](docs/figures) · [貢献ガイド](CONTRIBUTING.md) · [開発計画](PLAN.md) · [MIT ライセンス](LICENSE)

<a id="community"></a>

## 使ってみて、止まった場所を教えてください

<img src="docs/figures/community.svg" alt="再現可能な問題、成功した作業フロー、改善パッチを GitHub で共有。" width="100%">

[不具合を報告](https://github.com/yuki4266/ruin-everything/issues/new?template=bug.yml) · [使い方を共有](https://github.com/yuki4266/ruin-everything/discussions/categories/show-and-tell) · [機能を提案](https://github.com/yuki4266/ruin-everything/discussions/categories/ideas)

**ブラウザーに付き添う時間が減ったら、[スターで応援してください](https://github.com/yuki4266/ruin-everything)。**
