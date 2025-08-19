# of-lyre
适用于原神, 开放空间等游戏的乐器演奏程序, 支持延音

## 使用方法
- 以管理员身份运行gui.py
- 主界面四个按钮的作用分别是: 打开mid文件, 开始演奏, 停止演奏, 打开在线midi浏览器. 两个滑块用于决定起始位置和终止位置
- 点击开始演奏按钮后你有三秒钟时间将游戏切回前台(窗口焦点), 随后演奏开始. 建议使用窗口模式, 方便中途将程序切回窗口焦点
- midi浏览器的server程序位于[另一个储存库](https://github.com/byzp/Genshin-Lyre-midi-player-server/tree/main/server)
- 默认键位适配开放空间, 在程序同级目录新建key.txt并写入键位(原神:ZXCVBNMASDFGHJQWERTYU)时将覆盖原始映射, 修改后可用于其他游戏, 顺序是从低音到高音, 换行符将被忽略
- 觉得有用给个star吧🤗

## 注意事项
- 应该不会封号, 但不提供任何保证, 使用风险自负
- 仅适用于windows
- 如果游戏本体以管理员身份运行(被管理员进程拉起的也算, 比如通过taptap启动的), 则此程序也需以管理员身份运行
- 对于开放空间, 由于游戏本身的问题, 演奏者和听众听到的存在差异, 并且bpm越高越严重, 并非此程序的问题

## 一些有用的工具脚本(位于tools文件夹, 基本都是gpt写的)
- remove_lower_notes.py 移除所有起始时刻和时值相同的低音键, 保留一个最高音
- key_map_to_midi.py 将键盘谱(主要是原神的)转换为mid文件
- find_most_similar_midi.py 查找与指定mid最相似的mid
- humanize_midi.py 将mid中同时触发的note错开(of特化方案)

## 待办
- 多乐器的同步演奏
