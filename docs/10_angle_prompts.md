# 10. 顔の向きの差分（ChatGPT 用・第 2 弾）

目的: 顔を回したときに「平面の歪み」ではなく、描かれた角度の絵に沿って動かすための見本。
前回の 8 枚（15°・30° など）は絵としては良かったが、元の絵との差が大きすぎて、間をつなぐと崩れた。
今回は **小刻み（5° 刻み）で、頭だけが回った絵** を作る。

## 作り方の決まり（前回と同じ）
- 1 枚ごとに新しいチャットを開く。毎回、元の画像 `art/gen/input/upper_full.png` を添付する。生成結果を次の元にしない。
- ファイル名は下の表のとおり。`art/gen/output/` にアップロードする。
- 1 枚につき 2〜3 枚作って、いちばん元の絵に近いものを選ぶ。

## 共通の指示（毎回、先頭に貼る）
```
Edit the attached image. Rotate ONLY the character's head (face, hair, ear accessories, hair ornament) as described below.
Everything else must stay pixel-identical to the input: the torso, shoulders, jacket, necktie, the owl on the left shoulder, the long silver hair below the shoulders, the framing, the canvas size, and the white background.
The neck base and shoulders do not move. Keep the same facial expression (eyes open, closed neutral mouth), same line art, same coloring and shading, same hair strands and accessories as much as possible.
The amount of rotation must be small and exact, like turning the head a few degrees on a 3D model.
{EDIT}
```

## 差分ごとの指示（{EDIT} に入れる）
| ファイル名 | {EDIT} |
|---|---|
| `yaw_r05` | Turn the head 5 degrees toward the viewer's right (the character's left). |
| `yaw_r10` | Turn the head 10 degrees toward the viewer's right (the character's left). |
| `yaw_r15` | Turn the head 15 degrees toward the viewer's right (the character's left). |
| `yaw_l05` | Turn the head 5 degrees toward the viewer's left (the character's right). |
| `yaw_l10` | Turn the head 10 degrees toward the viewer's left (the character's right). |
| `yaw_l15` | Turn the head 15 degrees toward the viewer's left (the character's right). |
| `pitch_u05` | Tilt the head up by 5 degrees (chin rises slightly), no sideways turn. |
| `pitch_u10` | Tilt the head up by 10 degrees, no sideways turn. |
| `pitch_d05` | Tilt the head down by 5 degrees (chin lowers slightly), no sideways turn. |
| `pitch_d10` | Tilt the head down by 10 degrees, no sideways turn. |

最初は 10 枚です。うまくいったら、斜め（`yaw_r10` + 上下 5°）なども追加します。
