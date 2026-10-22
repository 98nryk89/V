# iPhoneの回転・正面付近の安定化 v2（2026-10-22）

利用者が実iPhoneで「下を向いても顔が回転しない」「正面へ戻した際にずれる」と報告したため、
新しい入力変換とHTMLを別ファイルで作成した。完成Webカメラ版・前のiPhone版・起動ファイル・中継・画像は変更しない。

## 原因として確認できた点

公式[受信サンプル](https://github.com/DenchiSoft/VTubeStudioBlendshapeUDPReceiverTest/blob/main/Assets/Example/VTubeStudioReceiveDataExample.cs)は
`Quaternion.Euler(-Rotation.y, -Rotation.x, Rotation.z)`で頭を描画する。
つまりRotation.xが左右、Rotation.yが上下。旧iPhone入力はこの二つを逆に解釈していた。
修正版はAngleX=-Rotation.x差、AngleY=Rotation.y差、AngleZ=Rotation.z差とする。
AngleYはモデルで上が正、UnityのX回転は下が正のため、上下の符号も区別する。
角度差は較正した姿勢からの度差で、左右/かしげ±5度、上5度/下10度の上限は変えない。

また、旧版の位置倍率10は公式の例に見られる程度の小数位置差を大きく増幅し、
raw位置が0.1変わるだけでBody値が最大へ達していた。v2では初期倍率を0.2に下げ、
位置差0.1以内、角度差0.35度以内の微小変化を除外する。
しきい値を超えた分だけ連続的に反映し、移動・回転の最大値や一般のスムージングは維持する。
これは新しいデフォルト設定であり、全iPhone・全環境で最適な値と確定したわけではない。

## 正面の記録

- 最初の顔は従来どおり仮の基準にする。
- Cキーでは直近約0.3秒の安定した複数フレームの中央値を使う。
- 大きく動いている間、再検出直後、データが古いときには記録を受け付けない。
- 角度の±180度境界をまたいでも中央値・角度差を正しく扱う。
- 顔を横に向け続けても勝手に正面の基準を動かさない。顔未検出時も既存の基準を保持する。
- 画面に記録の成功/静止を求めるメッセージを残し、入力確認と診断値コピーを追加。
  診断値はボタンを押したときにクリップボードへコピーするだけで、自動送信や画像記録は行わない。

実機側で生の位置・角度自体が変わる大きなドリフト、iPhoneを動かした際の座標の変化を、
この修正だけで全て除去できると断言しない。実機でなおずれる場合はiPhoneを固定し、正面の生値と基準値を比較する。

## 利用者への更新方法

配布ZIPは `dist/lunaris_iphone_pose_v2_update.zip`。実行ファイルを含まないHTML更新だけのセット。

1. 現在動いている `Lunaris_iPhone` フォルダをFinderで複製し、旧版として残す。
2. ZIP内の `owl_prince_iphone_test.html` と `owl_prince_tracking_config_v2.json` の**2ファイルだけ**を、
   現在使っている `Lunaris_iPhone/html` の中へ入れる。HTMLは置き換える。htmlフォルダ全体を交換しない。
3. 起動済みならモデル画面を再読み込みするだけ。未起動なら、既に許可した元の起動.commandを使う。
4. iPhoneを固定し、正面・閉じ口で0.3秒程度静止してからCを押す。「正面・真顔を記録しました」を確認する。
5. 下向き、左右、正面への復帰を試す。倍率が小さすぎる場合は画面の移動感度で調整する。

旧設定JSONやWebカメラ用JSは消さずに残す。起動ファイル・Node・中継の交換やnpm操作は不要。
戻すには複製した旧フォルダから元HTMLを戻す。新しい設定ファイルは旧HTMLからは使われない。

## 制作・検証

- 新入力：viewer/tracking-input-v2.js。旧viewer/tracking-input.jsは保存。
- 新UI：viewer/iphone-v2.html。旧viewer/iphone-test.htmlは保存。
- 新単一HTML：dist/owl_prince_iphone_v2.html。旧dist/owl_prince_iphone_test.htmlは保存。
- 新設定：dist/owl_prince_tracking_config_v2.json。旧設定は保存。
- 再出力：python tools/export_iphone_pose_v2.py。
- 更新ZIP：python tools/package_iphone_pose_v2_update.py。
- 単体検証：node --test tests/tracking_input_v2.test.cjs。
- 配布ZIPの実経路：python -m unittest tests/test_iphone_pose_v2_browser.py -v。

単一HTMLのrig・画像・メッシュ・物理は完成版から完全複製する。頭や髪の構成を作り直さない。
ブラウザ検証は前回配布したMac ZIPへ更新2ファイルを重ね、同じ中継から模擬iPhoneの公式軸データを送り、
下向きだけ、左右だけ、正面への復帰、微小な位置揺れ、口/瞬き/表情を確認する。
実iPhoneによる最終確認は利用者PCで必要。
