# c艹上机

> 原 PDF: knowledge/study/sources/year1/pdf/study-s2-programming-efb6bb2d624c4062.pdf
> 页码指 PDF 文件第 N 页，不冒充印刷页码。公式及手写内容须对照原 PDF。

## PDF 第 1 页 · 片段 1

试题 1 (A 卷 )
题目 1 # 145
题目描述
设计一个昼数类 C 。 mp | ex , 进行复数的运算 · 要求 :
( 1 ) 包含两个整数成员变量表示实囗慮部
( 2 ) 包含一个对所声明对象初始 《 酣勾造函数 。 不提供参数时 , 构造函数应提供默认值 ,
( 3 ) 用运算符更载的形式 , 实现以下跽作 : a) 两个 Comp 丨 e × 值加 , b) 两 °C omp 厄 × 值相减 , ( ) 两个
Complex 值相乘
( 4 ) 编写主函数 , 瀟 C 。 mp 厄 × 类 ·
输入
蟠入个 , 分别是两个复数的实部和部 ·
输出
以 a + bi 的形
第一行蝓匕两个昼数的和
第二行蝓匕两个数的差
第三行输匕两个后数的乘积 。
( 沌意 : 若最终结果为 0 , 则输出伍实部和慮部为 0 则不出 , 侨 2 + Oi , 就输出 2 : 0 + 3i , 则不输出实部自以及
: 阝的 + 号 , 直接输出 3i 。 若实部为正数 , 则不输出前面的 + 号 · 若慮部匕现 1 或者一 1, 则不输出 1 , 侨 8 + li, 应
直接蝓出 8 + 0
提示 :
数的跹念 : 我们把形如 z=a+bi ()s b 均为实数 ) 的数称为簋数 · 其中 , a 称为实部 , b 称为慮部 , i 称为慮数单
位 。 其中 , i 的平方等于一 1 。
特别注意 、
此题必须用类和运算符望载做 , 直出获得 AC 的同学 , 记 0 分 。
样例输入
样例输出
4 + 7i
. 31
. 6 + 14i

## PDF 第 2 页 · 片段 1

试题 1 (B 卷 )
题目 # 146
题目描述
设计一个复数类 Comp | ex , 进行簋数的运算 · 要求 :
( 1 〕 包含两个整数成员变量表示实訁囗慮部 ,
( 2 ) 包含一个对所声明对象初始 《 〕 构造函数 。 不堤供参数时构造函数应堤供默认值 ,
( 3 〕 用运算符载的形式 , 实现以下操作 : a) 两个 C 。 mp 《 e × 值植减 b) 两 °C 。 mp | e × 值加 ,
Complex 值相乘
( 4 ) 编写主函数 , %Y.Complex*.
输入
输入四个整数分别是两 . 个昼数的实部和部 ·
输出
以 a + bi 的形式
第一行输出两个昼数的差
第二行输匕两个复数的和
第三行输出两个昼数的乘积 。
0 两个
( 沌意 : 若终结果为 0 , 则蝓出伍实部和慮部丿则不出 , 侨 2 + Oi , 就输匕乙 0 + 3i , 则不蝓出实部白以及
〕 + 号 , 直接出 3i 。 若实部为正数 , 则不输出前面的十号 · 若慮步匕现 1 或者一 1 , 则不输出 1 , 例如 8 + li , 应
直接输出 8 + i )
提示 :
复数的念 : 我们吧形如 z=a+bi (a 、 b 均为实数 ) 的数称为复数 . 其中 , a 称为实部 , b 称为慮部 , i 称为数单
它其中 , i 的平方等于一 1 。
特别注意 :
此题必须朋类和运算符重载做 , 直出获得 AC 的同字 , 记 0 分 。
样例输入
2 2 2 5
样例输出
. 3i
4 + 71
. 6 + 141

## PDF 第 3 页 · 片段 1

试题 2 (A 卷 )
题目 | # 147
题目描述 :
请定义一一个象基类 Fi 丨 e 类 。 并派生 ±ChangeEncode_name* ( 更改文件编码和文件名 ) 类和
ChangeEncode size* ( 更改二文件编码和大刂嵝 ) 要求如
抽象基类 e 类 : 有俣护成民量 filename , esize 分别表示文件名 ( 字符串类型 } , 文件大小 ( 类型 ) , 纯
É±EUpdateFi le 0 和纯發函数 sh 。 w() , 参数和返回类型根据需要定义 。
派生 *ChangeEncode name 类 ChangeEncode size 类 : 新后成 RZ*fiIeEncoder ( 文件编码方式 ) 。 常见的
編码方式有四种 ("ASCII", "UN °C ODE", "UTF8TANSl") 。 用类型 0 , 1 , 2 , 3 分别作为 “ ASC 旷 ,
"UN °C ODE", "UTF8" 和 "ANSI" 的示讠己, 均为丿 〈 写字母
I. 自行添力酵与造函跷
艺 ChangeEncode name** 的 UpdateFile 0 函数用来更改文亻牛编码手囗文亻牛 · ChangeEncode size 类中的
UpdateFiIe 0 函数甲来更件编和文件大 / 」 、
3 . ShowO 来展示文件信息 : ChangeEncode name 类中展示的文亻牛信息格式为 : change_encodeAndname:2
件名文件大小文件编码方式用空格隔开 , 冒号前后无空格 , 如 : change_encodeAndname:Main.cpp 32
ASCII. ChangeEncode size 类中展示的文件后息格式为 : change_encodeAndsize:Ä 件名文件大小文件编
码方式用土悭隔开冒号前后无空 1 各如 : change_encodeAndsize:Main.cpp 32 ASCII.
输入 :
第一行为三个初始字段 , 文件名 , 文件大小 , 文件编码方式 。 其中文件名为字符串 ( 长度不超过 256 ) , 文件大小


## PDF 第 3 页 · 片段 2

deAndsize:Main.cpp 32 ASCII.
输入 :
第一行为三个初始字段 , 文件名 , 文件大小 , 文件编码方式 。 其中文件名为字符串 ( 长度不超过 256 ) , 文件大小
为整数文件编码方式为数字 0 ( 表示 ASCI 码 ) , 1 ( 表示 UN °C ODE 编码 ) , 2 ( 表示 UTF8 编码 ) 或 3 ( 表示 AN 引
第二行首先输入一个字符 , 代表要进行的操作 :
如果输入字符是 " No , 代表要灯文件进行编码转和更名作 , 接下来一行是更改后的文件名和编码 ;
如果输入字符 " 孓 ( 大写 ) 代表要对文件进行编码转和更改大小操低接下来一行是更改后的大刂码 ·
输出 .
采用用动态联编的方式 , 蝓出文件更新启的信息 , 如果蝓入的撲作字符 《 0 No 和 “ , 贝出 ' ' No such
operation! “
必须采用象基类必须实现继承和多态 , 否则计 0 分 ·
样例输入 :
NKLJ nice_every_day. txt 4321 e
Good luck .txt 1
样例输出 、
change_encodeAndnane : GOOd luck. txt 4321 UNICODE

## PDF 第 4 页 · 片段 1

试题 2 (B 卷 )
题目 | # 1
题目描述 :
请定义一一个拍象基类 Fi | e 类 , 并派生出 Cha ngeEncode_name* ( 更改文件编码租文件名 ) 类和
ChangeEncode size* ( 更改文件编码和大小类 ) 要求如下 ·
抽象基类 Fi | e 类 : 有俣护成员变量 filenan , 和 esize 分别表示文件名 ( 字符串类掣 ) , 文件大小 〈 皇类型 ) , 纯
É±äUpdateFile 0 和纯数 sh 。 w() , 参数和返回类型根据需要宁义一
派生 *ChangeEncode name*ChangeEncode ' e 类 : 新成 ( 文件编码方式 ) 。 常见的
编码方式有四种 ("UN °C ODE". "ASCII", "ANSI " 和 "UTF8") 。 用类型 0 , 1 , 乙 3 分别作为 “ U NICODE",
"ASCII", “ ANS 「 和 “ UTF8 “ 的标讠己均为大写字母
1. 自行添加沟造数 。
艺 ChangeEncode name*#z 的 UpdateFile 0 函数用来更改文件编码和文亻牛名 。 ChangeEncode size*•c# 的
UpdateFile 0 数甲来更改文件编码和文件大刁 、
3 . ShowO 来展示文件 1 百皂 , ChangeEncode name 类中展示的文亻牛信息格式为 : change_encodeAndname:2
亻牛名文件大小文件编码方式用空格隔开冒号前后无空格如 : change_encodeAndname:Main.cpp 32
ASCII. ChangeEncode size 类中展示的文件 1 百格式为 : change_encodeAndsize:Ä 件名文件大小文件编
码方用悭隔开冒号前后无空格如 : change_encodeAndsize : Mai n.cpp 32 ASCII.
输入 :
第一行为三个初始字段 , 文件名 , 文件大小 , 文件编码方式 : 其中文件为字符串 ( 长度不超过 256 ) , 文件大小


## PDF 第 4 页 · 片段 2

Andsize : Mai n.cpp 32 ASCII.
输入 :
第一行为三个初始字段 , 文件名 , 文件大小 , 文件编码方式 : 其中文件为字符串 ( 长度不超过 256 ) , 文件大小
为整数文件编犸方式为数字 0 ( 表示 IJ N °C ODE 编码 ) , 1 (表示 ASCII*) , 2 (表示 ANS 《 编码 ) 或 3 (表示 UTF8
编码 ) 。
第二行首先蝓 / \ 一个字符 , 代表要进行的操作 :
如果蝓少 、 、 字符是 " N “ , 代表要灯文亻牛进行编石鬱奐和更作 , 接下来一行是更茂舌的文件和编码 ;
如果蝓少 、 、 字符 " 孓 ( 大写 ) 代表要对文件进行编码转痪和更改大小操低接下来一行是更葭的大刂痢编码 ·
输出 :
采用动态联编的方式 , 输出文件更新后的信息 , 如果输入的操作字符非 ' No 稽孓 , 则输出 “ N 。 such operation ! “
注意 :
必须采用象基类之须实现继承和多态 , 否卿分 。
样例输入 :
NKlJ_nice_every_day . txt 4321 e
00d luck.txt 1
样例输出 .
change_encodundnane : GOOd_luck . txt 4321 ASCII

## PDF 第 5 页 · 片段 1

试题 3 (A 卷 )
题目丨 # 149
题目描述
设计如下样式的链表类模板 》 ist , 并对其进行简单使用 ·
template < ( 1a55 T> class 1 st {
/ / 类析 st , 使用类型形参 T
struct node {
/ / 结构体 node 类型用来定义糙表表 ! 页 ( 的具体掘项 )
T data;
/ / 每一表项的 data 掘域的类型由类型形参 T 所指定
node next;
/ / 过指针 next , 多个表项 “ 誕摘 ” 成一个表
} *head, ta 1 ;
/ / 成员 head 与 t 1 , 为表的首尾指针
public :
list 0 ; / / 构造函 , 创逮 “ 空表 ”
/ / 生成表项届入到原的首
VO lnsert (T item) ;
void Append (T item) ; / / 生成表页晡加到原的尾
int count 0 ;
void htot();
void ttoh();
void display();
void SortList();
/ / 返回当前表的页
/ / 把表首项移到尾
/ / 把表尾项移到首
/ / 将各表 IÄ 额掘 data 显示在屏蓽上
/ / 将各表 ! 页掘 data 排序后显示在屏幕上
八个成员数的具体功能庙述如下 :
1 , list 0 ; 构适凼数 , 将 head 与 tail 均置为 NULL, 意味菩创建出一个 “ 空链表 “ ·
艺 void | nsert (T item); 动态牛成一块链表项空间 , 并将 T 类型的数据 item 放入该涟表项的 data 域 , 而后将新
生成的该逆表项适入到原链的链首 ( 链表的 “ 栈 “ 用法 ) 。
土 void Append (T item); 动态生成一块链表项空间 , 并将 T 类型的数 item 放入该链表项的 data 域 , 而后将
新生成的该链表项附加到原琏的链尾 ( 逆表的 “ 队列 “ 式用法 ) 。
生 int count(); “ 数出 “ 荇返回当前逆表的数据项数 : 空链时返回 0 ; 链表非空时 , 意味菩要 “ 历 “ 逆表 , 即从头到


## PDF 第 5 页 · 片段 2

链尾 ( 逆表的 “ 队列 “ 式用法 ) 。
生 int count(); “ 数出 “ 荇返回当前逆表的数据项数 : 空链时返回 0 ; 链表非空时 , 意味菩要 “ 历 “ 逆表 , 即从头到
尾 “ 数 “ 出链表的项数后返回 ·
5 . void htot0; 吧链表首项移到尾 : 空链亚仅一项时无须移动 ; 否则 , 要将原链首项 “ 接到 “ 其尾项之后 , 而后马
上啁整新逆首指针 head 以及新链尾指针 tail.
& void ttoh(); 吧链表尾项移到琏首 : 空链仅一项时无须移动 ; 否则 , 要将原链尾项 “ 挪到 “ 链首 , 而后马上啁整
新链首指针 head 以及新尾指针 tail.
7 . void d ispIayO; 将各链表项数据 data 显示在屏幂上 : 空逆时输出 •emptylist• ; 否则要对链表进行 “ 遍历 “ , 从
头到尾逐项对其 data 数据进行显示 ( 输出元寮之间用一个空格隔开 ) ·
& void SortList();
将各琏表项数据 data 排序后显示在鼾幂上 : 首先按照链表的数据从小到大顺孛 (ÉASCI | 码排序 ) 进行排序 ,
并将其输出的果 ·

## PDF 第 6 页 · 片段 1

要求 :
在主函数中 , 需要创建两 、 链表 linkl 和 | ink2 , 将蝓入的所有琏表元素依次通过 Ap 四 nd 加到 | inkl 中 , 并依次通过
lnsert 加到 Iink2 中 · 之须用逆表实现 , 否则 0 分 :
输入
蝓入厂其肖三行 , 第一一行为链表类型 〔 只需考劇 n har , 均为刂即可 ); 第二行丿表长度 : 第三行依次蝓少 、 链
表元蔬
输出
输出有七行 :
第一行为 | inkl °C ountO 白果
第二行为 IinkI.display0$S 吉果,
第三行为 linkl 乬亘 ttoh0 后 , linkl.display() 的结果;
第四行翔 ink2 , ( ountO 白果
第五行为 No k2 , disp | ayO 白吉果 ,
第六行为 Iink2 经过 htotO 后 , link2.display0 的结果 ;
第七行为 linkl 或 &link2 So 戊 List0 的结果
样例输入 1
int
5
S 2 彐 4 1
样例输出 1
5 2
3 4 1
1 5
2 3 4
5
1 4 3
2 S
4 3
2 5 1
1 2
3 4 5
样例输入 2
Char
3
样例输出 2
3
b
3
a b

## PDF 第 7 页 · 片段 1

试题 3 (B#)
题吕 ] # 150
题目描述
十如下棰酗逆表类板 t , 并对其进行筒单使用 .
template <Class T> class 115t {
/ / 模 list , 使用类形 T
struct node {
/ / 詁构 node 类型用定义链表项 ( 的具恤数据项 〕
T data;
/ / 与一项的 data 数据敏的类型由芸型形参 T 所指定
node * next ·
/ / 过指针 next , 将多个項 “ 链熙 ” 成一个链
} *head, ai1 ;
/ / 敷据砹员 head 与 tail' 为链的百过指针
public :
list 0 ; / / 构造函敷 , 创建 “ 链 “
/ / 生砹链袅项 0 入到杀链的链百
VOid lnsert (T iten
void APPend (T iten) ; / / 生成顼附到柰链的链过
int count();
VOid htot();
VOid ttoh() ;
VOid display() ;
VOid SortList() ;
/ / 返生丽链表的项数
/ / 吧链表百顼移到过
/ / 吧链表过顼移到链百
/ / 将各表项据 data 显示在丰上
/ / 旃各链项据 data 排产后且示在上
八个成员数的具功 《 旨菡述如下 :
1 . 0 : 构适函数将 head 与 tail 均置为 NULL, 意味苷创建出一个 " 空涟表
2 . void | nsert 任 item); 动态生成一块链表项空司 , 荇将 T 类型白戈据 item 放少 、 该链表项的 data 域 , 而后将新
生成的该表项后入 . 到原钅 0 涟首 ( 逆表的 ' 栈试牖却 。
3 , void Append 仃 item); 动态生成一块链表项空间 , 并将 T 类型的数据 item 放 . 入该逆表项的 data 域 , 而后将
新生成启 0 该表项附加到原逆的涟罨 ( 《 连了 ' 队列 ' 式用法 〕 。
4 , int count0 : “ 数出 “ 并返回当前链表的数据项数 : 空返回 0 ; 链表韭空时@ 意味要 ' ' 沮亓链表 , 即从头到


## PDF 第 7 页 · 片段 2

的涟罨 ( 《 连了 ' 队列 ' 式用法 〕 。
4 , int count0 : “ 数出 “ 并返回当前链表的数据项数 : 空返回 0 ; 链表韭空时@ 意味要 ' ' 沮亓链表 , 即从头到
数 “ 出链表的 ; 爻舌返回 ·
5 . void htot0,• 把链表首项移到琏尾 : 空或仅一顶时无须移动 ; 古则 , 要将原琏首项 ' ' 接到 “ 其尾项之后 , 而后马
上调整新逆首指针 head 以及新葩尾指针 tail.
6 . void ttoh0; 把链表尾项移到首 : 空或仅一项时无须移动 : 古则 , 要将原涟尾项 ' ' 挪到 “ 逆首 , 而后马上啁整
新首扌旨针 ' head 以及斤链尾指针 ' tail.
7 . void display0; 将各逆表项数据 data 显示在屏草上 : 空逆时蝓出 · emp i ; 古则要对逆表进行 " 遍历 " , 从
头到尾逐项灯其 data 数据进行显示 ( 蝓出元素之间用一个空格隔开 ) 。
8 . void SortListO;
将各表项数据 data 排序后显示在屏草上 : 首先按照涟 」 数据从大到 / . 卜顺序 ( 按 ASCI | 码排序 ) 进行排序 ,
并将其蝓出的结是
要求 .
在主函数中 , 需要创建两个链表 | inkl 和 | inQ , 将蝓入的所有链表元素依次通过 Ap 四 nd 加到 《 inkl 中 , 并依次通过
lnsert 加 *JIink2 中 . 必须用表实现 , 否则 0 分 .

## PDF 第 8 页 · 片段 1

输入
. 一其有三行 , 第一一行为逆表类型 〔 只需考慮 in har , 均为小写即可 ): 第二行为表长度 : 第三行依次蝓入道
表元
输出
输出有七行 :
第一彳亍为 | inkl £ ountO 的结果
第二行为 | inkl .dispIay()ä%É4 :
第三行为 | inkl 经过 ttoh0 后 , linkl .display() 的结果
第四行为 | ink2 . count0 的结果
第五行为 | ink2 , disp | ay 舶吉果 :
第六行为 | ink2 经过 htot0 后 , Iink2.dispIayO 的结果
第七彳亍为 | inkl 或 Slink2 SortListO 的纟吉果
样例输入 1
int
5
样例输出 1
5
5 2 3 4 1
5
1 4 3 2 5
4 3 2 5 1
5 4 3 2 1
样例输入 2
char
3
样例输出 2
3
3
《 a b

## PDF 第 9 页 · 片段 1

附加题 Nku_s1 m e 的魔法阵
题目 | # 151
题目背景
在鞘三次世齐核平战争结束后 Nku 一 slmp 丨 e 回到了自己的家园 , 在战舌的和平时间里 , 为了肝御邪恶的
Siannodel 的入儡, Nku 一 slmp 丨 e 专门出了趟远门 , 拜访了竄女久远寺有诛与苍崎青子向她们适教了 0 〕 使用
方法 · 在一段时间的字习之舌 , Nku 一 slmp 字会了使用两去 ·
就在 Nku 一 slmp ] e 准备向两亻立女告别之际 , Siann 。 de 丨而着他手下的邪恶思去师又向 Nku 一 slmple 与久远寺宅邸宣
战了 , 战事一触即发 ! Nku 一 slmp 被安蚂壬务是在宅邸正门布置到去阵进行防御工作 。
战事紧急 !
题目描述
0 去阵是一个 . n * n 的矩阵 , 初始状态是没有竄力的 , 可以认为魔力都为 0 , 因为对竄力的掌控能力不足 ,
Nku 一 slmp 丨 e 每次施氵去只能选择去阵的冥一一行或一一列 , 使它有啲魔力同时长 x , 在施法结束后 , Nku_s1mple
养的 0 去猫味 Tsip sE 河气地跳上了 0 去阵破坏了其中一块 0 蕊因为施法次数过多 , Nku_s1mpleEÆ 不记得
那炔地方被沲加了多少麾力了 , 亻帮他吗 ?
输入描述
第一一行包含一一个 n , 表示麾去阵的大小为 $ n 丶 times n$.
接下来 n 行 , 亍包含 n 个 , 表示酃 0 竄力 .
题目俣证 0 去阵中只有一个数是一 1 , 表示被破坏的魔氵
输出描述
蝓出 . . 一行一一个聖数 , 表示被破坏的 0 去在被破坏前的魔力 ·
沌意 : 请在蝓出答后输出一价车 / 空行 , 以俣证格式正确 .
样例
样例输入
3
样例输出
1
数据范围
亻杲讠正 SI \ leq n\leq 2eøø,-1\1eq a 一 { 1 }\leq leeøeees , : 并 § . 有且 1 有一 “ 个一 { 島 j } : . 巧 。

## PDF 第 10 页 · 片段 1

A卷第一题(BY LuHaozhe)
#include <iostream>
using namespace std;
class Complex {
int shi;
int xu;
public:
Complex() {
shi = 0;
xu = 0;
}
void input(int a,int b) {
shi = a;
xu = b;
}
friend Complex operator+(Complex& a, Complex& b)
{
Complex temp;
temp.shi = a.shi + b.shi;
temp.xu = a.xu + b.xu;
return temp;
}
friend Complex operator-(Complex& a, Complex& b)
{
Complex temp;
temp.shi = a.shi - b.shi;
temp.xu = a.xu - b.xu;
return temp;
}
friend Complex operator*(Complex& a, Complex& b)
{
Complex temp;

## PDF 第 11 页 · 片段 1

temp.shi = a.shi * b.shi - a.xu * b.xu;
temp.xu = a.shi * b.xu + b.shi * a.xu;
return temp;
}
void output() {
if (shi == 0) {
if (xu == 0) {
cout << "0" << endl;
}
else {
cout << xu << "i" << endl;
}
}
else {
if (xu == 0) {
cout << shi << endl;
}
else {
if (xu > 0) {
cout << shi << "+" << xu << "i" << endl;
}
else {
cout << shi << xu <<"i" <<endl;
}
}
}
}
};
int main() {
int a1, a2, b1, b2;
cin >> a1 >> a2 >> b1 >> b2;
Complex com1;

## PDF 第 12 页 · 片段 1

Complex com2;
Complex com3;
Complex com4;
Complex com5;
com1.input(a1, a2);
com2.input(b1, b2);
com3 = com1 + com2;
com3.output();
com4 = com1 - com2;
com4.output();
com5 = com1 * com2;
com5.output();
return 0;
}
A卷第二题(BY JiangFengyi)
#include<iostream>
#include<string>
using namespace std;
class File
{
protected:
string filnname;
int filesize;
public:
File(string name, int size) :filnname(name),
filesize(size) {};
virtual ~File() {};
virtual void UpdateFile(int encoder, string newname) =
0;
virtual void UpdataFile(int encoder, int newsize) = 0;
virtual void show() = 0;

## PDF 第 13 页 · 片段 1

};
class ChangeEncode_name : public File
{
int fileEncoder;
public:
ChangeEncode_name(string name, int size, int
encoder) :File(name, size), fileEncoder(encoder) {};
void UpdateFile(int encoder, string newname)
{
fileEncoder = encoder;
filnname = newname;
}
void UpdataFile(int encoder, int newsize)
{
fileEncoder = encoder;
filesize = newsize;
}
void show()
{
cout << "change_encodeAndsize:" << filnname << "
" << filesize << " ";
switch (fileEncoder)
{
case 0:
cout << "ASCII";
break;
case 1:
cout << "UNICODE";
break;
case 2:
cout << "UTF8";
break;

## PDF 第 14 页 · 片段 1

case 3:
cout << "ANSI";
break;
}
cout << endl;
}
};
class ChangeEncode_size :public File
{
int fileEncoder;
public:
ChangeEncode_size(string name, int size, int encoder)
:File(name, size), fileEncoder(encoder) {};
void UpdataFile(int encoder, int newsize)
{
fileEncoder = encoder;
filesize = newsize;
}
void UpdateFile(int encoder, string newname)
{
fileEncoder = encoder;
filnname = newname;
}
void show()
{
cout << "change_encodeAndsize:" << filnname << "
" << filesize << " ";
switch (fileEncoder)
{
case 0:
cout << "ASCII";
break;

## PDF 第 15 页 · 片段 1

case 1:
cout << "UNICODE";
break;
case 2:
cout << "UTF8";
break;
case 3:
cout << "ANSI";
break;
}
cout << endl;
}
};
int main()
{
string filename;
int filesize;
int encoder;
cin >> filename >> filesize >> encoder;
char ch;
cin >> ch;
if (ch == 'N')
{
ChangeEncode_name file(filename, filesize,
encoder);
cin >> filename >> encoder;
file.UpdateFile(encoder, filename);
file.show();
}
if (ch == 'S')
{
ChangeEncode_size file(filename, filesize, encoder);

## PDF 第 16 页 · 片段 1

cin >> filesize >> encoder;
file.UpdataFile(encoder, filesize);
file.show();
}
}
A卷第三题(BY Luhaozhe)
#include<iostream>
#include<string>
using namespace std;
template <class T>
class list {
struct node {
T data;
node* next;
};
node* head;
node* tail;
public:
list() : head(nullptr), tail(nullptr) {}
void Insert(T item) {
node* newNode = new node;
newNode->data = item;
newNode->next = head;
head = newNode;
if (tail == nullptr) {
tail = head;
}

## PDF 第 17 页 · 片段 1

}
void Append(T item) {
node* newNode = new node;
newNode->data = item;
newNode->next = nullptr;
if (tail == nullptr) {
head = tail = newNode;
} else {
tail->next = newNode;
tail = newNode;
}
}
int count() {
int count = 0;
node* current = head;
while (current != nullptr) {
count++;
current = current->next;
}
return count;
}
void htot() {
if (head != nullptr && head != tail) {
node* firstNode = head;
head = head->next;
tail->next = firstNode;
firstNode->next = nullptr;
tail = firstNode;
}
}

## PDF 第 18 页 · 片段 1

void ttoh() {
if (head != nullptr && head != tail) {
node* lastNode = tail;
node* current = head;
while (current->next != tail) {
current = current->next;
}
current->next = nullptr;
tail = current;
lastNode->next = head;
head = lastNode;
}
}
void display() {
if (head == nullptr) {
std::cout << "emptylist";
} else {
node* current = head;
while (current != nullptr) {
std::cout << current->data << " ";
current = current->next;
}
}
std::cout << std::endl;
}
void SortList() {
if (head != nullptr && head != tail) {
node* current = head;
node* index = nullptr;
T temp;

## PDF 第 19 页 · 片段 1

while (current != nullptr) {
index = current->next;
while (index != nullptr) {
if (current->data > index->data) {
temp = current->data;
current->data = index->data;
index->data = temp;
}
index = index->next;
}
current = current->next;
}
display();
}
}
};
int main() {
string listType;
cin >> listType;
int length;
cin >> length;
if (listType == "int") {
list<int> link1;
list<int> link2;
for (int i = 0; i < length; i++) {
int item;
cin >> item;

## PDF 第 20 页 · 片段 1

link1.Append(item);
link2.Insert(item);
}
cout << link1.count() << endl;
link1.display();
link1.ttoh();
link1.display();
cout << link2.count() << endl;
link2.display();
link2.htot();
link2.display();
cout << "Sorted List: ";
link1.SortList();
} else if (listType == "char")
{ list<int> link1;
list<int> link2;
for (int i = 0; i < length; i++) {
char item;
cin >> item;
link1.Append(item);
link2.Insert(item);
}
cout << link1.count() << endl;
link1.display();
link1.ttoh();

## PDF 第 21 页 · 片段 1

link1.display();
cout << link2.count() << endl;
link2.display();
link2.htot();
link2.display();
cout << "Sorted List: ";
link1.SortList();
}
return 0;
}

## PDF 第 22 页 · 片段 1

B 卷第一题一求圆形的周长和面积
题目丨 # 635
题目描述
编与程序 , 定义一个圆形的类 , 求圆形的周长和面积 , 规定丌亠 3 · 14 。
输入
1 个正整数 , 代表圆形的半径 。
输出
圆形的周长 L , 面积 S , 均是 doub 丨 e 类型 ,
样例输入
3
样例输出
18 . 84 28 · 26
以空格分隔 , 行尾无空格
必须用类实现周长和面积的计算函数 , 否则计 0 分 。
数据保证计算结果在 double 表示范围内 。
题目描述
某水果店为了促销 , 制定了如下的定价策略 , 尸代表某种水果的单价 , V 铲代表购买某种水果的重量苹果 : 打八
折 , 需支付尸 * W * 0 . 8 元 , 香蕉 : 半价 , 需支付 P * H72 元 , 橘子 : 如果 V 犷 > = 10 , 则打半价 , 即需支付
W * 尸 / 2 元 ; 如果厂 > = 5 , 则打七五折 , 贝刂需支付厂 * 尸 * 0 . 75 元 , 其它情况不打折 。
请你编写一个抽象基类 Fr t , 包括 2 个保护成员 , 分别是尸 ce ( 单价 , 类型 ) 、 ' e 匆五 ( 重量 , 类
型 ) 。 定义纯虚函数 5 榄 rn 。 “ e 黟 , 用于计算顾客购买的水果总价 。 以丆 r 榄作为基类 , 派生出 , 4 e 、
Banana 、 Orange 类 , 实现计算顾客购买水果总价的功能 。
输入
多行 , 每行格式为 C 尸 , 中间用空格分隔 , 分另刂代表水果类型 、 b 、 。 分别代表苹果 、 香蕉 、 橘子 ) , (
忉 t 型 ) 、 尸 (int 型 ) 分别代表顾客购买的相应水果的重量和单价 。 输入字符结束输入 。
输出
购买的水果的总价 。
样例输入
b 15 5
样例输出
92 “ 85
注意
必须实现抽象基类 、 多态 、 动态联编 、 否则计 0 分 。

## PDF 第 23 页 · 片段 1

题目描述
假设你有一个简单的单向链表 , 链表的节点包含一个整数值 ( 大于等于 0 , 且小于 10 ) 。 现在 , 你需要重载 + 运算
符 , 使得两个链表可以进行一种特殊的相乘操作 : 反转相乘具体规则如下 .
1 , 首先将两个链表分别反转 。
2 . 然后从头节点开始 , 对应位置的节点值相乘 。
3 . 如果链表长度不等 , 较短的链表后面的缺失值视为 10
4 . 如果相乘的结果大于等于 10 , 则进位到下一个节点继续参与计算 ( 如果不存在则创建一个新节点 〕 。
例如 , 链表 , 4 为 5 2 3 , 链表 B 为 4 5 6 , 反转后分别为 3 2 5 和 6 5 4 , 相乘后的链表为 8 1 1 2 ( 因为 3 * 6 = 18 ,
进亻立 1, 2 * 5 + 1 = 11, 进位 1 , 5 * 4 十 1 = 21 , 进位 2 〕 。
要求
1 . 定义链表节点结构体 0 N 包含整数值省和指向下一个节点的指针 “ “ t 。
2 . 定义链表类 0 “ dLi , 需要重载 + 运算符 , 使其接受两个链表头节点作为参数 , 并返回反转相乘的链表头
节点 。
引再 0 “ 炖 dLi 类中编写辅助函数用于反转链表以及输入 、 输出函数 。
4 . 如果 . 4 或者 B 为空链表 , 则返回另一链表的反转链表 ; 如果 “ 4 和召同为空链表 , 则返回 NU 力 L 。
输入
第一行为链表 , 4 ,
第二行为链表 B ,
其中空链表 NU 刀无表示 。
输出
反转相乘后的结果
样亻列输入 :
输出
反转相乘后的结果
样例输入 :
5 2 3
4 5 6
样例输出 :
8 1 1 2

## PDF 第 24 页 · 片段 1

题目描述 : 请编写实现一个湮的 M 黟 S 忉砝 ( 栈 , 后进先出 L F 仂模板类 , 该模板类实现了一个能够存储常见数
据类型 @馄, 、 ) 的栈 , 栈最大容量 M 天 LEN 为 20 。 该模板类形式及主要成员函数如下
template<class T>
class MyStack{
MyStack(T 引 、 ray[], 1 nt len);
VOid push( const &T value);
T pop 0 ;
b001 empty 0 ;
int count();
void shO 闪 0 ;
void clear();
/ / 构造函数 , 根据数组构造
/ / 入栈
/ / 出栈
/ / 空栈判断
/ / 栈中成员数
/ / 打印栈 , 打印栈中所有元素和元素个数 , 空格分隔
/ / 清空栈
完成该模板类及成员函数之后 , 请在襯 a 0 函数中验证 , 验证要求和方式如下 .
1 、 定义两个数组 , 整数类型数组和字符类型数组 , 分别初始化为固定数值 , 然后利用这两个数组进行构造类对
象 , 数组如下格式 :
int iarray 冂
{ 2 , 3 , 5J7J11J13 , 17 丿 19 , 23 丿 29 。 31J37 } ;
( h a r carray[ ]
"this is a teststring ;
/ / 整数数组 , 初始数据固定
/ / 字符数组 , 初始数据固定
2 、 从标准输入端读取操作标记符和操作数 , 操作符和操亻乍标记如下 ( 第一个字符为操作标记符 , 后面的为操作
输入操作要求说明 :
d 展示栈 , 栈列输出 " N “ e " 执行 “ , 0 方法打印栈数据和元素个数
5 终止操亻乍此栈无输出信息
让操作数入栈无输出信息 , 若栈满则输出 " FULL "
s 终止操作此栈无输出信息
让操作数入栈无输出信息 , 若栈满则输出 " FU '
。 从栈中出队个元素 , 为类型无输出信息 , 若处理到空栈则输出 " N “ e “
3 、 栈有容量限制 M 天 LE , 因此 , 在栈已满时 , 入栈将无法进行 , 直接输出 “ 丆 U 力 0 。 同样 , 当栈为空时玄


## PDF 第 24 页 · 片段 2

无输出信息 , 若处理到空栈则输出 " N “ e “
3 、 栈有容量限制 M 天 LE , 因此 , 在栈已满时 , 入栈将无法进行 , 直接输出 “ 丆 U 力 0 。 同样 , 当栈为空时玄
再执行出栈操作时栈将无数据 , 直接输出 1 次 "None"0
程序输入
程序输入为两行 , 第一行为类型栈的操作序列 , 第二行为对 c 五 “ 类型栈的操作序列 ,
符栈的入栈字符不会出现 ' ' 空格字符 ) 。
程序输出
依次为输入操作码对应的输出信息 , 用空格分隔 。
行均以 s 结尾 ( 字

## PDF 第 25 页 · 片段 1

第一题 : 链表合并 (A 卷 )
题目 《 #969
题目痛述
给定一个荜链表 , 将奇数蘇号目佰为奇数的节点和偶数旧号目值为偶数的节点分别聚集 。 并輸出合卉后的新链
蒜要求必须使适表结构实现 。 并通 0 运箅符重载完成输入输出 。
1 . 节点编号规则 : 首个节点视为奇数节点陲号的 , 第二个节点视为偶数节点 ( 编号 2 ) , 以此类准
2 . 转换输出 : 奇数链表在前 《 偶数链表在后 《 输出合并之后的结果涟磊奇数节点组和偶数节点组需保持原始相
对顺序
3 . 特殊处理 ' 链表为空时输出 . NIJLL"
实现要求
1 . 之须自定义表结构 , 包含节点类 Node 和链表 AinkedList
2 . 必须 0 载 > > 运算符实现链表入 · 重我 < 运符实现涟表滞出
3 . 之须实现 rearrange() 方法完成奇偶节点重
格式为 :
层 1 自 2 ·
( M 为节点个数 , A AM 为各节点整数值 , M = 0 时表示空链表 )
输出
输出重组后的链表 , 节点间空格分 。 耒尾无空格 。
空链表输出 。 NLJLL%
样例输入
样例输出
第一题 : 链表合并 (B 卷 )
题目 # 970
题目描述
给定一个单适表 》 请将奇数号目值为奇数的节点和偿数号且值为偶数的节点分别聚笑 《 芬出合荇后的新链
恶要求之须使用适表结构实现 。 羿通 i 篁运算符重载完成输入输出 ,
1. 节点蘇号规则 : 首个节点视为奇数节点 〔 号 1 〕 , 第二个节点视为健数节点 〔 编号 2 ) 》 以此类推
2 . 转换出 : 偶数表在前 , 奇数适表在后 , 输出合芬之后的结果链表孬奇数节点组和偎数节点组需保原始相
对顶序
3 . 特殊处理 : 链表为空时输出 . NLJLL"
实现要求
1 . 之须自定义链表结恂 。 包含点 *Node 和 ü*LinkedList
2 . 之重载 > > 运符实现链输入 , 重载 < < 运箅符实现韃表输出
3 . 之实现 re 酊 range() 方法完成奇偶壭点到非
输入
格式为
( M 为节点个数 , A AM 为各节点整驯自 , M = 0 时表示空链表 〕
输出


## PDF 第 25 页 · 片段 2

载 < < 运箅符实现韃表输出
3 . 之实现 re 酊 range() 方法完成奇偶壭点到非
输入
格式为
( M 为节点个数 , A AM 为各节点整驯自 , M = 0 时表示空链表 〕
输出
输出市组后的链表 , 节点间空格分隔 。 未尾无空格 。
空链表输出 。 NULL “
样例输入
样例输出
题目配置 》
题目名 . 第一题 : 链表合并 (A 卷 )
编号 : % 9
测过点 : 10
时门限制 : 1 OOO ms
空间限制 . 6 KiB
完成状态 : 已通过
过率 . 1 5 5 / 1348
评测全部测试点 : 是
Special Judge: 未启用
三快涑啭 》
A . 第一题链表合并 (A 卷 )
提交题目
提交记录
题目配置 》
题目 : 第一题 : 链表合并阳卷 )
编号 : 970
測试点 : 10
时间限制 : 1000 ms
空间限制 》 655 KiB
完成状态 》 未提交
过率 : 1 1 1 / 12
评测全部晁试点 . 是
Special Judge: 未启用
= 快速啭 》
B . 第一题 : 链表合并 ( B 卷 〕
提交题目
提交记录

## PDF 第 26 页 · 片段 1

第二题 :
交通工具相赁系统 ( A 卷 〕
题目 》 # 971
题目扌苗述 :
设计一一 i 、 交通 : 0 到岳系铳 , 该糸统能够管理不同类型交通工到的信息和彗用计 . 系铳需要支持以下功能 :
~ 基类设计 . 创建一个名为 Vehicle 的逋象基类 , 包含以下成员 :
纯虚函数 doub 《 e calculateRentalFee(int days): 十算峤且 fé 用 、 亻尿 1 户拒员变量 : bra n d ( 品牌 ,
型 ) 、 model ( 型号 , stringæm
2 、 构造函数和虚忻构函数 ;
土纯虚函数丷 。 id displaylnfo 0 用于蝓出每种交工具的信息 ·
~ 派生实现 : 从 Vehicl 生出 1 以 ] 《 鼻亻本 :
、 Car ( 汽车 〕 : 包含座亻属性 (seats, int 型 〕 , 赁用为基 i 出用 200 己 / 天 + 座 《 数 × 10 元 / 天 ,
品牌 、 型号 ,
乙
土
Motorcycle ( 摩多乇车 〕 : . 包含扫 E 量厘性 ( “ , int4!) , 彳且 1 月 」 为扫 《 量 x 住 5 元 / 天 ;
Bicycle ( 0 行车 ) : 包含是否电动属性 (isElectric, int#!, 0 表示非电动 , 1 表示申动 )
, 申动自行车相黛彗甲
为 50 元 / 天 , 普自行车为 20 氵亡 / 天 。
i 1 長戔叾是目要求 。 十算刁 ; 同种类交通工貝的忄且赁用 。
第一 . 彳一个整数 N , 4 弋表有 N 彳亏交工貝 B 信息 。 接下来的 N 行 , 0 行 5S 个数 , 分别是 1 剖 0 」 二貝的种类 (Cft*
汽车 。 M 亻弋表摩托车 , B 代表自彳了车 ) . 该种交 i 重工 , 爿的總 . 型号 、 私柯届性 、 礻且 1 孬丿 (int!V)
分隔 ·
输出 .
N 行 , 按照题目要求 《 用毖数 d 这 p y 《 nf0 输出首 、 交 i 二 L 具的种类 (Car. M0torcycle 、 Bicycle)


## PDF 第 26 页 · 片段 2

丿 (int!V)
分隔 ·
输出 .
N 行 , 按照题目要求 《 用毖数 d 这 p y 《 nf0 输出首 、 交 i 二 L 具的种类 (Car. M0torcycle 、 Bicycle)
以及私有属性信息 ( 只有是 Bicycle 时才输出 ) , 其中是否为电动属性 , 是输出 true, 否则输 ± 饷 ] 艹 ,
“ lculateRenta 下 ee 函数输出才目赁用 , 各个处居之 . 间用仝各分 . 隔 , 彳亍亻无仝格
样例输入 .
C byd qin 5 2
侗 haojue 獄 FR12SX 15e 1
E Gxant Quxck-E 3
样例输出 :
Car byd qrn 7ee
Motarcyc1e haojue 应 FR125X 7 5
BicycIe Giant QuiCk-E fa1S 6e
要求 : 顿实现继承和多态 , 之须实现抽象基类和动态联否贝刂计 、 ·
第二题 . 交通工具租赁系统 (B 卷 )
题目 《 # 972
题目描述
, 中间空格
设计一个交通工具相赁系统 。 i 亥系统能够笪理不同类型交通工具的相赁信息和用计的 · 系统需要支持以下功能 :
、 基类 i 殳计一创建一一个名为 Vehicle 的象基类 , 包含 L; 丿 、 . 卜 》 员 :
1 , 纯虚 doub calculateRentalFee(int days): 十算 § 1 用 , 《 呆扌户 0 苋员变量 : brand ( 品裨孬 string*
型 ) model (型号@ string*N)
构造函数和虐析构函数 ;
纯虚函为交丷 oid displaylnfo 0 用于输出每和 : 甬工 : 的信息 。
派生类实现 . 从丷 ehicle 派生出以下具体类 :
、 Car ( 汽车 ) : , 包含座伛 7 属性 (seats, int 型 ) , 租彗角为基石出用 200 元 / 天 + 座 1 数 × 1 5 元 / 天 ;
厶
Motorcycle ( 摩托车 ) : 包含排量属性 ( ( 匚 , int 型 ) , 相赁费用为排量 x2 元 / 天 ;


## PDF 第 26 页 · 片段 3

 200 元 / 天 + 座 1 数 × 1 5 元 / 天 ;
厶
Motorcycle ( 摩托车 ) : 包含排量属性 ( ( 匚 , int 型 ) , 相赁费用为排量 x2 元 / 天 ;
eicycle ( 自行车 ) : 和含是召 : 申动属性 (isElectric, int4!, 0 表示 」 E 电动 , 1 表示 E 皂云丿月
, 电动自彳了车且 ! 用
为 40 元 / 天 , 普通 0 行车为 20 元 / 天 ·
谲根据题目要求 , 计算不同种类交湮工具的泪赁费用 “
输入 :
第一行一一个整数 N 。 代表有 N 行交通工具的信息 , 接下来的 N 行 , 每行有 5 个数据 。
汽车 。 M 代表摩吒车 , B 代表国彳亍车 ) 该种交 i 工貝的品悝型号枞私有厘性对
分阝
输出 :
分别是接湮工具的种类 ( C 代表
忄目 1 吉梦攵 (int#!) , 中佃 」 用 0 格
一题目配置 》
题巨名 : 《 二二是 : 交 i 堡工 0 礻貝后系统 (A#)
测试点 : 10
时间限制 : 10 佣 m s
空了司限制 : 65536 KiB
完巧茈准犬态 : 已渔过
通过率 : 220 / 1686
评測全部癱试点 , 是
Special Judge : 耒启月丬
三快速跳转 》
E . 第二题 : 交 i 工 ! 剮系统 (A 卷 :
提交题目
提交记录
题目酉己 》
题目名 : 第一题 : 交通工貝租赁糸统 (B 卷 )
纟号过 972
测试点 : 10
时间限制 : 1000 ms
空间眼制 : 65536 KiB
完成状态 : 未提交
通过率 : 253 / 1624
评测全部试点 : 是
Special Judge: ! 耒启虍
= 忄求孬专 》
F. 第二题交通工具租赁系统 (B 卷 )
提交题目
提交记录
N 行 , 按照题目要求调用函数 display | nf 。 输出 0 个交通工貝的种类 (Car 、 Motorcycle 、 Bicycle) 、 品牌 、 型号 ,
以及私有属性信息 ( 只有是 Bicycle 时才满出 〕 孬其中是否为电动属性孬是蝓出 Tru 否则输出 False, 调用


## PDF 第 26 页 · 片段 4

、 Motorcycle 、 Bicycle) 、 品牌 、 型号 ,
以及私有属性信息 ( 只有是 Bicycle 时才满出 〕 孬其中是否为电动属性孬是蝓出 Tru 否则输出 False, 调用
calculateRentalFee 函數满H岳且I盖些用, 各个數据之间用空格分隔 。 彳亍有冫丿己空 《
样例输入 :
C byd qin 5 2
haojue 众 FR12SX 159 1
B Giant Quick- E 9 3
样例输出 :
〔 a 广 byd qin 55e
Motorcycle haojue 应 FR125 × 32a
B1cyc1e G 1 ant Qu1Ck-E Fa1se 69
要求它颚实现继承和多态 , 它须实现抽象基类和动态联编 , 否则计 0 分 。

## PDF 第 27 页 · 片段 1

第三题 : 容器模板类 (A 卷 )
题目丨 # 973
题目描述 ·
请蕪与实现一^ 容器模板类 MyContainer, 该模板类实现了一个能够存储常见数据类型 ( int,float*ßchar) 的基本
容器 , 该椏板类的主要形式和成员函数如下
C1a55 T>
CI 茜 S 雪 MyContainer{
myContainer 、 (T arr 、 ay[], int Ien );
VO d dd ( consf &T
题目配置 》
题目名 : 第三题 : 容器模板类 (A%)
编号 . 973
测试点 : 10
/ / 构造函 , 根冕数组造
/ / 添加元紊鋥容器末尾
b001 remove(int idx) ;
b001 empty( ) ;
void display();
vo d clear();
/ / 删除指定位置的兀素 , 删賒成功谌回 ture , 位置越界诓回 f 炉
/ / 空容器判断
/ / 返回当前容器大小
/ / 打印容器 , 打印容器中所有元素 , 格式
元素 1 元素 2
/ / 清空睿器
时间限制 :
空间限制 :
完成状态
1000 ms
65536 KiB
已湮过
完成该模板类及成员函数之后 , 请在 main() 函数中验证 , 验证要求和方式如下
1 、 定义三个数组 , 整数类型数组 、 浮点数數据类型和字符类型数组 , 分别初始化为固定数亻虬然后利用这两个
组进行构造类对象 , 数组如下格式
/ / 数数组 , 初始敖据固定
int iarrayt]
{ 2J3J5J8J13 , 21 34 55J89 } ,
/ / 浮点数组 , 初始为固定值
flaat farray [ ] = { e , ø . 125 , e . 25 》 0 . 375Je . 5 , e . E25 e . 75 , e . 875J1 . e } ;
/ / 字符数经 , 初始为固定值
char carray[)
10v@ Nankai university
2 、 从输入端读取操作标记符和操作数 , 作符和操作标记如下 ( 第一个字符为操作标记符 , 后面的 × 为作数 )
输入操作要求
d
c
打印容器信息
终止操作此容器


## PDF 第 27 页 · 片段 2

ai university
2 、 从输入端读取操作标记符和操作数 , 作符和操作标记如下 ( 第一个字符为操作标记符 , 后面的 × 为作数 )
输入操作要求
d
c
打印容器信息
终止操作此容器
把操作数追加到容器末尾
执行 disp ay() 方法打印容器数据 , 容器为空输出 “ N 。 n
无输出信息
无输出信息
。 × 从容器中删除位置为 × 的元素无直接输出信息 , 若处理到空容器则输匕 “ N 。 ne "
äx 越界输出 "BoundsLimit"
清空当前容器
无输出信息
程序输入 :
程序输入为两行 , 第一行为对 int 类型容器的操作序列 , 第二行为对 f | 。 at 类型容器的操作序列 , 第三行为对字符类型
容器作的序列 ( 字符类型操作序列中的操作数不会出现空格字符 ' ' 〕 , 每一行均以 s 结尾 。
程序输出 :
依次为输入操作码对应的输出信息 ·
样例输入 、
d 0 4 d s
1 1 . 25 d 0 13 S
d 1 5 d 土 d d c 0 27 5
样例输出 :
[ 2 , 1J1 》 2 , 305 》 8J13 , 21 34J55J89 ]
[ 3JIJ1 》 2J5 8 , 13,21, 彐 4 , 55J89 ]
〔 3 . 125J3 . 25 . 375 . 5J3 . E25J3 . 75 , . 87s 1J1 . 25
BoundsLimit
[ I 一 O, e 是
u,n,i,v,e,r.sß.t.y,s,d 〕
第三题 . 容器模板类 (B 卷 )
题目丨 # 974
题目描述 :
请写实则一一 1 、 容器模板类 MyContainer, 该忄莫反类实现了一个能鸲 1 诸南见数据类型 (int,float 和 char) 的基本
容器 , 该模板类的王要形式和成员函数如下 :
template<cla
cias MyConeainer•{
MyContainer(T 00 「 ay 〔 ] 0 1 n ) ;
/ / 构造数 , 根扼数组构造
/ / 追加元素到容器水尾
VO d append( const &T value) ;


## PDF 第 27 页 · 片段 3

{
MyContainer(T 00 「 ay 〔 ] 0 1 n ) ;
/ / 构造数 , 根扼数组构造
/ / 追加元素到容器水尾
VO d append( const &T value) ;
VOåd 10 ( 亡 T& 巫 lu 》 Lnt idX ) ; 丿 / 1 还 , 入丿亡紊 valu
到指定的位 dx , 炻又为位置菘号 。 容器的位置号从 a 丌始
b001 empty( ) ;
VO d 0i5p1 y 〈 ) ;
VOåd 亡 1 ar ( ) ;
/ / 窄 # 器月 0
/ / 返回当前容器大小
/ / 打 〔 卩冰器 , 打印容器中所有元素 。
/ 丿清空容器
格式 ,
元素 1 元素 2
巧划亥 1 莫忄反类及 0 苋员一丞复之后 , 在 main() 数中验证 , 驸讠正要求和方亍如下
1 、 定义三 · 个豐殳绢 , 整类型数泪 、 浮只巨数数 1 居类型和字很王类型数纟且 , 分别初始匕为固生 《 划直 ,
组进行构造类对象孬数组如下格式 .
/ / 整數数组 , 初帕数琚固定
int ]
{ 》 10102 , 3 5 , 8 》 13021034 55 30 } ;
户杰后利这两个数
float far 「 ay 门过 { a . 12 到 a . 2 到釓 37 到 e 巧 e . 525 諧 e . 75 , a . 87 六 1 . e}; / / 浮点数数组 , 初始为固定值
/ / 字符数组 · 初始为圃定值
亡 ha 广
10M Nankai
乙从输入端读取操作标记符和操作数 , 操作符和操作标记如下 ( 第一一个字符为操作标记符 , 后面的 x 为作数 )
输入操作要求
d
a ×
打印容器信息
终止擬作此容器
把 1 乍婺 × 追加到容器末尾
说明
执行 sh 。 w() 方法打印容器数据 , 容器为空输出 “ N 。 ne "
无輸出信息
无输出信息
i × id × 把 1 笮划忝氵忝加容器的 idx 位首无出信息 , 若 idx 亻首越界 , 她输出 "BoundsLimit"
通过率 : 64 / 1352
评测全部测试点 : 是
Special Judge : 耒启用
三快涑跳转 》


## PDF 第 27 页 · 片段 4

idx 位首无出信息 , 若 idx 亻首越界 , 她输出 "BoundsLimit"
通过率 : 64 / 1352
评测全部测试点 : 是
Special Judge : 耒启用
三快涑跳转 》
C 第三题 . 容器模板类 ( A 卷 〕
提交题目
提交记录
颛目配置 》
题目名 . 第三题 : 容器模板类卷 )
纟@号过 974
测 《 i 点 : 10
时间限制 :
1 OOO ms
空间限制 。
。 65s36 KiB
完成状态 : 耒提交
通 i 寸率 : 75 / 1004
评测全部测试点 : 是
Special Judge : 未启庄
三快速跳转 》
D . 第三题 : 容器模板类 (B*)
提交题目
提交记录
( 空当前容器
程序输入 。
无出信息

## PDF 第 28 页 · 片段 1

程序输入 :
程序输入为三行 , 第一行为对 int 类型容器的作序列 , 第二行为对 f ] 。 at 类型容器的作序列 , 第三行为对字筲类型
容器操作的序列 ( 字符类型操作序列中的作数不会出现空恪字符 ' 0 , 一行均以 5 结尾 。
程序输出 :
依次为输入操作码对应的输出信息 。
样例输入 :
d 4 d 匚 d 5
气 ! 28 5
样例输出 :
[ 》 1J2 丿 3 , 冫 1J34 」 55J89 ]
[ , 1 》 10 是 03 , 5 , 吕 , 13 , 21 , 3 啤 055 , 吕 9 , 4 ]
None
[ 2 , 3 . 1250e . 25 譴 . 375 生 . 50e . 525 , 2 . 750a . 87501 譴 1 . 25 ]
. 1 . 125 . 25 . 375 是 . 5 . 525 . 75 . 875 1 1 . 25 ]
[ 島
》 1 0 。 v , e , 一 , N 。 a n , k 》 a 。 飞 ,
》 u 。 n , 。 V 。 e , 广 。 s 譴飞 , t , y ]
附加题 : Knight of Nights
题目 《 # 975
题目描述
作为拥有操纵时间程度的能力的女仆 , 十六夜呋夜可以将大量飞刀丢 ± 后暫停时间 , 从而形成一 ^ 完美的飞刀阵 。
在坐标轴上孬飞刀的轨泌可以看作是无限多等间距的 、 与 y 轴平行的直线 , 而飞刀阵则是一个简单多边形 〔 可能是
凹的 ) 。
呋夜想在阵中布满飞刀 。 于是她想知 . 在飞刀阵的到定范围内 , 所有飞刀的轨迹的长度之和是多少 。
为防止飞刀出现在阵的边缘导致攻击无效 , 保证多边形的任意一条边均不与 y 轴平彳同时为方便起见 , 总有一条
轨迹直线恰好与 y 轴重合 ·
输入
第一行输入一个数字代表多边形的边数 。
接下来的 n 行 , 每行用空格开两个实数 , 按照顺时针顺序给出多边形的 “ ( 3 “ 飞 105 ) 个顶点的坐标
, ( 一 104 , 势 104 ) : 第个点与第 i + 1 个点连接 〔 1 孓 ,
后一行给出轨迹的间距 0 彐孓孓 1 開 ).


## PDF 第 28 页 · 片段 2

出多边形的 “ ( 3 “ 飞 105 ) 个顶点的坐标
, ( 一 104 , 势 104 ) : 第个点与第 i + 1 个点连接 〔 1 孓 ,
后一行给出轨迹的间距 0 彐孓孓 1 開 ).
输入数据的浮点数 , 均保留 4 位小数 ·
输出
对于每个样例输出一行 。 包含一个数字 , 表示多边形内包含的线段长度和 。
若你的答案 0 “ 5 的与标准答案 std 满足 . @艹 ,@ < 10 一 6 , 则被认为止确 ,
rna-r(1.0,std)
样例输入 1
2.eoee 2 .
2 · 5 一 2 .eøeo
. 2 . 50e9 . 2 .
. 2 . øeee 2 . e299
样例输入 2
第 ” 个点与第 1 个点连接 。
因此谲保留铰多的小数位数 。
题目配冒 》
题目名 : 附加题 : Knight of Nights
综号 . 975
测试点 : 5
时间限制 : 1 0 m s
仝间限制 : 256000 KiB
完成状态 : 未提交
通率 : 2 / 77
评测全部测试点 : 否
Special 」 udge: 比较丬莫式
三快速跳转 》
G . 附加题 . Knight of Nights
提交题目
提交记录
3 . 1329
。 7875
1 . 4 S
1 . 3s39
. 4 . s584
一 9 . 1554
7475
S. 2818
-e . 7937
. 8 . 413E
. 4 . 7s59
. 3 . 3224
L3199 . s742
一 5 . aøee
. 2 . 2324
8 . 1791 e . 4321
2 . 1978 4 38E4
1 . 4741
样例输出 2
85 , 27378E1924
