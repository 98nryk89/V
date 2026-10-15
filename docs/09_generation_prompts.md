# 09. 差分画像の生成プロンプト（ChatGPT 用）

方式 B の素材作り。元の絵を ChatGPT の画像編集で少しずつ変えた「差分」を作る。こちらで元の絵との差を取り、パーツと動きの基準にする。

## 先に知っておくこと: 顔の向きの差分は「見本」に使う

顔を動かしたときにぼやけるのは、角度ごとの絵を半透明で切り替える作り方をした場合です。この計画では、**角度ごとの絵は表示に使いません。** パーツを変形して角度を作り、角度の差分は「この角度ではこの形になる」という見本（寸法の基準）にします。iki には、正面と横向きの絵から回転の量を測って、変形をそれに合わせる機能があります。

- **目・口・眉**: 差分を細かく作ります（目は 100/75/50/25/0%）。中間の状態も変形でつなぎますが、見本が多いほど自然になります。
- **顔の向き**: 15° 刻みの見本を作ります。多少の描き崩れは、寸法を測るだけなので問題になりません。

## 使う元画像（リポジトリの `art/gen/input/`）

| ファイル | 用途 |
|---|---|
| `face_crop.png` | 顔まわりの切り抜き（1024×1024）。**顔の差分は、すべてこれを元にする** |
| `upper_full.png` | 上半身の全体（1144×1375）。髪・フクロウの差分に使う |
| `guide_eyes.jpg` / `guide_mouth.jpg` / `guide_brows.jpg` / `guide_eyes_brows.jpg` | 編集する範囲を赤で示した見本（ChatGPT の範囲選択を使うときの目安） |
| `mask_*.png` | API で生成するとき用のマスク（ChatGPT アプリでは使わない） |

## ChatGPT での作り方（ずれを防ぐための決まり）

1. **差分 1 つにつき、新しいチャットを開く。** 同じチャットで続けて頼むと、前の結果を元に描き直されて、絵がだんだんずれていきます。
2. **毎回、元の画像（`face_crop.png` か `upper_full.png`）を添付する。** 生成された画像を、次の元にはしないでください。
3. 下の **「共通の指示」と「差分ごとの指示」をつなげて**貼り付ける（共通の指示の `{EDIT}` の所に、差分ごとの指示を入れる）。
4. 画像の範囲選択（ブラシで塗って、その部分だけ直す機能）が使えるときは、`guide_*.jpg` の赤い範囲を塗ってから指示を送ると、ずれがさらに減ります。使えなければ、指示だけで構いません。
5. **1 つの差分につき 2〜3 枚作る**（「もう一度」で作り直す）。良いものをこちらで選びます。
6. 保存するファイル名は、下の表の名前に `_1`、`_2` を付けたもの（例: `eye_50_1.png`）。

### 結果の送り方
- いちばん良いのは、GitHub のリポジトリの `art/gen/output/` に、「Add file → Upload files」でまとめてアップロードする方法です（画質が落ちない）。
- チャットに添付してもらっても使えます。ただし、圧縮で画質が少し落ちる場合があります。

## 共通の指示（毎回、先頭に貼る）

```
Edit the attached image. Change ONLY the following: {EDIT}
Everything else must stay exactly the same as the input image:
- same canvas size and aspect ratio, same framing and zoom, no cropping
- same head position, same head angle, same face shape
- same hair strands, same accessories, same earrings
- same line art thickness and color, same anime coloring and soft shading style, same lighting
- same plain white background
Do not redraw, restyle, smooth, sharpen, or move anything outside the edited area.
The edited area must match the original art style exactly, as if drawn by the same artist.
```

## 第 1 弾（必須）: 目・眉・口・顔の下地・前髪

元画像は、すべて `face_crop.png` です。

### 目（範囲: `guide_eyes.jpg`）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `eye_75` | both eyes 75% open: lower both upper eyelids slightly. Keep the iris color, pupils, highlights and the lash line shape. |
| `eye_50` | both eyes half open (50%): lower both upper eyelids so they cover the top half of the irises. Keep the lash line shape and thickness. |
| `eye_25` | both eyes almost closed (25% open): upper eyelids lowered so only a thin sliver of iris is visible. Keep the lash line shape. |
| `eye_closed` | both eyes gently closed and relaxed: each eye becomes a single soft downward-curved lash line with lashes, at the position of the current lower lid. No iris or white visible. |
| `eye_smile_closed` | both eyes closed in a happy smile: each eye becomes an upward-curved arch line (like ^ ^) with lashes. No iris or white visible. |
| `eye_wide` | both eyes wide open in surprise: upper eyelids raised, the whole round iris visible with white showing above and below the iris. |
| `eye_smile` | gentle smiling eyes: lower eyelids pushed up slightly so the eyes look softly narrowed from below. Irises still visible. |
| `eye_no_iris` | remove the irises and pupils from both eyes, leaving only the plain white of the eyes with the same eyelids and lashes. |
| `eye_no_hair` | remove only the hair strands that cross over both eyes, and complete the eyes, eyelids and lashes underneath them. |

### 眉（範囲: `guide_brows.jpg`）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `brow_up` | both eyebrows raised higher in surprise, same thickness and color. |
| `brow_angry` | both eyebrows lowered and angled down toward the nose (inner ends lower), an angry frown, same thickness and color. |
| `brow_troubled` | both eyebrows with the inner ends raised and the outer ends lowered, a worried, troubled look, same thickness and color. |
| `brow_none` | remove both eyebrows completely and fill with matching skin. |

### 口（範囲: `guide_mouth.jpg`）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `mouth_smile` | the closed mouth becomes a gentle closed-mouth smile (corners slightly raised). Same line color and thickness. |
| `mouth_frown` | the closed mouth becomes a slight frown (corners slightly lowered). Same line color and thickness. |
| `mouth_open_small` | the mouth slightly open, a small opening showing a hint of the upper teeth. |
| `mouth_a` | the mouth open as when saying "ah": rounded opening, upper teeth visible at the top, tongue visible at the bottom. Small, natural size for this face. |
| `mouth_a_keyed` | the mouth open as when saying "ah", same size as a natural "ah" mouth. Fill the ENTIRE inside of the mouth with one flat pure green color #00FF00 (no teeth, no tongue, no shading), keep the lip line around it. |
| `mouth_interior` | replace the whole image with only the inside of an open anime mouth: upper teeth at the top and a tongue at the bottom, dark red throat, centered, on a plain white background, nothing else. Same art style. |
| `mouth_none` | remove the mouth line completely and fill with matching skin. |

> `mouth_interior` だけは、顔ではなく「口の中だけ」の絵を作ります（共通の指示の「同じ構図」とは矛盾しますが、そのまま貼って構いません）。

### 顔の下地（範囲: `guide_eyes_brows.jpg` と `guide_mouth.jpg` の両方）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `face_blank` | remove both eyes, both eyebrows and the mouth completely, and fill those areas with smooth skin that matches the surrounding skin color and soft shading. Keep the nose line, the face outline, the hair and everything else. |

### 前髪（範囲指定なし）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `no_bangs` | remove the front bangs that hang over the forehead and eyes, revealing the full forehead, both eyebrows and both eyes. Keep the hair on the top, sides and back of the head, and keep the hair ornament. |

## 第 2 弾: 顔の向きの見本（範囲指定なし）

元画像は `face_crop.png`。**表示には使わず、寸法の見本にする**ので、多少崩れても構いません。「右」「左」は、**見ている人から見た向き**です。

| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `turn_r15` | rotate the head about 15 degrees toward the viewer's right (a slight three-quarter view). Turn the face, hair and hair ornament together as one solid head. Keep the neck and the head size the same. |
| `turn_r30` | rotate the head about 30 degrees toward the viewer's right (a three-quarter view). Turn the face, hair and hair ornament together as one solid head. Keep the neck and the head size the same. |
| `turn_l15` | 上の `turn_r15` の「right」を「left」に変えたもの |
| `turn_l30` | 上の `turn_r30` の「right」を「left」に変えたもの |
| `look_up15` | tilt the head back so the face looks about 15 degrees upward. Turn the face, hair and ornament together. Keep the head size the same. |
| `look_down15` | tilt the head forward so the face looks about 15 degrees downward. Turn the face, hair and ornament together. Keep the head size the same. |
| `turn_r15_up15` | rotate the head about 15 degrees toward the viewer's right and 15 degrees upward at the same time. Turn the face, hair and ornament together. |
| `turn_r15_down15` | rotate the head about 15 degrees toward the viewer's right and 15 degrees downward at the same time. Turn the face, hair and ornament together. |
| `turn_l15_up15` / `turn_l15_down15` | 上の 2 つの「right」を「left」に変えたもの |

首のかしげ（傾き）は、絵を回すだけで作れるので見本は不要です。

## 第 3 弾: 母音の口・表情の見本・フクロウ

### 母音の口（範囲: `guide_mouth.jpg`、元画像 `face_crop.png`）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `mouth_i` | the mouth as when saying "ee": wide and flat, teeth slightly visible. |
| `mouth_u` | the mouth as when saying "oo": small, rounded and pushed forward. |
| `mouth_e` | the mouth as when saying "eh": medium open, wider than tall. |
| `mouth_o` | the mouth as when saying "oh": round and taller than wide. |
| `mouth_laugh` | a big open laughing mouth, corners raised, upper teeth and tongue visible. |

### 表情の見本（範囲指定なし、元画像 `face_crop.png`）
仕上がりを確認するための完成見本です。
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `expr_smile` | the facial expression becomes a gentle, warm smile (soft smiling eyes and a closed-mouth smile). |
| `expr_surprised` | the facial expression becomes surprised (eyes wide open, eyebrows raised, mouth slightly open). |
| `expr_angry` | the facial expression becomes angry (eyebrows lowered toward the nose, eyes narrowed, mouth a tight frown). |
| `expr_troubled` | the facial expression becomes troubled and worried (inner ends of the eyebrows raised, a small uneasy mouth). |

### フクロウ（元画像 `upper_full.png`）
| ファイル名 | {EDIT} に入れる指示 |
|---|---|
| `owl_eyes_closed` | only the small owl on the shoulder: close both of the owl's eyes (relaxed closed eyes). |
| `owl_removed` | remove the small owl from the shoulder completely and draw the shoulder, jacket and hair that were behind it. |
| `owl_only` | replace the whole image with only the small owl from the shoulder, same pose and same size and position, on a plain white background. |

## 枚数の目安

| 弾 | 差分の数 | 1 つにつき 2〜3 枚で |
|---|---|---|
| 第 1 弾 | 21 | 約 40〜60 枚 |
| 第 2 弾 | 10 | 約 20〜30 枚 |
| 第 3 弾 | 12 | 約 25〜35 枚 |

まず第 1 弾を作ってください。届いたものから、こちらで位置合わせと取り出しを進め、うまくいかない差分があれば、プロンプトを直して再依頼します。
