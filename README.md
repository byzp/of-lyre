# of-lyre
适用于开放空间, 原神等游戏的乐器演奏程序, 支持延音

需要帮助? 或只是聊聊天? 加入qq群( ˘ᵕ˘ ):
```
891559070
```

## 使用方法(独奏, 有ui, gui.py)

<p align="center">
<img width="690" height="272" alt="image" src="https://github.com/user-attachments/assets/aaa9a485-5849-44e3-b650-c2c5e144cd99" />
</p>

- 点击开始演奏按钮后你有三秒钟时间将游戏切回前台(窗口焦点), 随后演奏开始. 建议使用窗口模式, 方便中途将程序切回窗口焦点
- 运行目录存在key.txt时将采用其映射, 修改后可用于其他游戏, 顺序是从低音到高音, 换行符将被忽略
- 主界面四个按钮的作用分别是: 打开mid文件, 开始演奏, 停止演奏, 打开在线midi浏览器. 两个滑块用于决定起始位置和终止位置
- 在线曲库界面一个谱子的三个按钮的作用是: 加载谱子, 下载谱子到指定位置, 删除谱子. 搜索框右边的按钮用于清除搜索, 需要搜索请输入名称并按下回车. 右下角可以上传midi谱, 上传需要输入上传者名称和密码, 随便输即可, 删除midi文件时仅验证密码


## 使用方法(合奏(仅支持21键乐器), 无ui, controller.py, agent.py)
- 在受控机上运行agent.py, 配置好可访问的端口, 将游戏置于窗口焦点
- 运行controller.py, 传入在线曲库地址和受控机暴露的api地址, 输入hash后三秒演奏开始, 输入"s"停止受控端并暂停演奏队列, 输入p继续
```
# 获取歌曲和对应hash
curl http://139.196.113.128:1200/latest_songs?page=1
# 启动被控程序
python controller.py --port 5000
# 启动主控程序
python controller.py --base-url http://139.196.113.128:1200 --agents http://192.168.0.113:5000 http://192.168.0.110:5000
```
- 含有note事件的轨道数量大于等于2时会自动拆分, 按顺序分配到所有可用的受控端, 目标轨道数超过受控端数量时剩余轨道会被分配到最后一个受控端
- 含有note事件的轨道数量等于1时, 目标轨道会被分配到最后一个受控端
- 对于overfield, 最后一个受控端建议控制电子琴
- 将controller.py内的auto变量设为True即可自动循环演奏

## 注意事项
- 应该不会封号, 但不提供任何保证, 使用风险自负
- 仅适用于windows
- 有些乐器的音域是c4-b6, 但程序控制时一律视为c3-b5, 使用的mid也必须满足此要求
- 如果游戏本体以管理员身份运行(被管理员进程拉起的也算, 比如通过taptap启动的), 则此脚本也需以管理员身份运行
- 成功的操作没有明显的提示, 点着看起来没反应是正常的, 但某处文字会被更改, 主要是主界面顶层按钮的下一行文字
- 由于大家使用的字符编码不同, 汉字可能出现乱码, 因此界面使用英语(在线曲库可能还是会乱码, 稍后解决)
- midi浏览器的server程序位于[另一个储存库](https://github.com/byzp/Genshin-Lyre-midi-player-server/tree/main/server)
- 觉得有用给个star吧🤗

## 一些有用的工具脚本(位于tools文件夹, 基本都是gpt写的)
- remove_lower_notes.py 移除所有起始时刻和时值相同的低音键, 保留一个最高音
- key_map_to_midi.py 将键盘谱(主要是原神的)转换为mid文件
- find_most_similar_midi.py 查找与指定mid最相似的mid
- humanize_midi.py 将mid中同时触发的note错开(of特化方案, 已弃用)
- transpose_midi.py 移调
- shrink_silences.py 将长静音替换为给定的最大时长
- process_black_keys.py 将黑键上移或下移一个半音
- estimate_pitches.py 输入音频, 判断音高
- split_deleted_notes.py 输入两个mid, 将不同时存在的note作为新轨道, 与旧轨道合并为新输出
- batch_midi_transpose.py 自动移调, 根据c3-b5的白键率, 低于c3的键的比例, 高于b5的键的比例筛选符合条件的mid, 使用--min_within_pct 0.95 --max_above_pct 0 时得到的结果一般是可以直接用的
- batch_midi_transpose_mt.py 多线程版本, mid非常多时可显著提高效率

## 其他脚本(位于scripts文件夹)
- auto.py 循环演奏文件夹内的所有mid文件, 需要导入core模块, 没有ui
- auto_online.py 循环演奏在线曲库的所有mid, 需要导入core模块, 没有ui

## 待办
- 电钢琴映射

## 界面
<p align="center">
<img width="732" height="333" alt="image" src="http://139.196.113.128:1160/img/gui.png" />
</p>
<p align="center">
<img width="728" height="568" alt="image" src="http://139.196.113.128:1160/img/online.png" />
</p>
