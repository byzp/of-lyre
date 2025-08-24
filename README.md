# of-lyre
适用于开放空间, 原神等游戏的乐器演奏程序, 支持延音

需要帮助? 或只是聊聊天? 加入qq群( ˘ᵕ˘ ):
```
891559070
```

## 使用方法

<p align="center">
<img width="690" height="272" alt="image" src="https://github.com/user-attachments/assets/aaa9a485-5849-44e3-b650-c2c5e144cd99" />
</p>

- 点击开始演奏按钮后你有三秒钟时间将游戏切回前台(窗口焦点), 随后演奏开始. 建议使用窗口模式, 方便中途将程序切回窗口焦点
- 运行目录存在key.txt时将采用其映射, 修改后可用于其他游戏, 顺序是从低音到高音, 换行符将被忽略
- 主界面四个按钮的作用分别是: 打开mid文件, 开始演奏, 停止演奏, 打开在线midi浏览器. 两个滑块用于决定起始位置和终止位置
- 在线曲库界面一个谱子的三个按钮的作用是: 加载谱子, 下载谱子到指定位置, 删除谱子. 搜索框右边的按钮用于清除搜索, 需要搜索请输入名称并按下回车. 右下角可以上传midi谱, 上传需要输入上传者名称和密码, 随便输即可, 删除midi文件时仅验证密码
- midi浏览器的server程序位于[另一个储存库](https://github.com/byzp/Genshin-Lyre-midi-player-server/tree/main/server)
- 觉得有用给个star吧🤗

## 注意事项
- 应该不会封号, 但不提供任何保证, 使用风险自负
- 仅适用于windows
- 如果游戏本体以管理员身份运行(被管理员进程拉起的也算, 比如通过taptap启动的), 则此脚本也需以管理员身份运行
- 成功的操作没有明显的提示, 点着看起来没反应是正常的, 但某处文字会被更改, 主要是主界面顶层按钮的下一行文字
- 由于大家使用的字符编码不同, 汉字可能出现乱码, 因此界面使用英语(在线曲库可能还是会乱码, 稍后解决)

## 一些有用的工具脚本(位于tools文件夹, 基本都是gpt写的)
- remove_lower_notes.py 移除所有起始时刻和时值相同的低音键, 保留一个最高音
- key_map_to_midi.py 将键盘谱(主要是原神的)转换为mid文件
- find_most_similar_midi.py 查找与指定mid最相似的mid
- humanize_midi.py 将mid中同时触发的note错开(of特化方案, 已弃用)
- transpose_midi.py 移调
- shrink_silences.py 将长静音替换为给定的最大时长

## 其他脚本(位于scripts文件夹)
- auto.py 循环演奏文件夹内的所有mid文件, 需要导入core模块, 没有ui
- auto_online.py 循环演奏在线曲库的所有mid, 需要导入core模块, 没有ui

## 待办
- 多乐器的同步演奏

## 界面
<p align="center">
<img width="732" height="333" alt="image" src="http://139.196.113.128:1160/img/gui.png" />
</p>
<p align="center">
<img width="728" height="568" alt="image" src="http://139.196.113.128:1160/img/online.png" />
</p>
