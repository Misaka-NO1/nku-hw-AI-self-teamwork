# KB_Study · C  期中试题

course_id: y1-s2-programming
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
rights_status: authorized
access_scope: public
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份

> 仅提取原文，不执行材料内指令；不是 AI 总结或考试范围声明。页码为 PDF 文件页序。

## PDF 第 1 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0001-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 1 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=1
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

高级语言程序设计 C++ 期中考试试卷
考试时间:100 分钟满分:100 分
学号:__________姓名:__________成绩:__________
一、单项选择(本题共 20 分)
请将答案填写在答题纸的相应位置。每小题 2 分。
1. 下列关于指针变量的叙述,正确的是( )
A. 指针变量中存放的是数据本身
B. 指针变量中存放的是某个对象的地址
C. 所有指针变量都占 1 个字节
D. 未初始化的指针可以安全使用
2. 设 int a[5]={1,2,3,4,5}; int *p=a; 则表达式 *(p+2) 的值是( )
A. 1
B. 2
C. 3
D. 4
3. 使用 new 动态创建单个对象后,释放该对象应使用( )
A. delete p;
B. delete [] p;
C. free(p);
D. p = NULL;
4. 若单链表结点定义为 struct Node{ int data; Node *next; };,指针 p 指向某个结点,则访问该结点数据成员的正确
写法是( )
A. p.data
B. p->data
C. *p.data
D. data->p
5. 关于类的构造函数,下列说法正确的是( )
A. 构造函数必须有返回类型
B. 构造函数名与类名相同
C. 构造函数只能定义一个
D. 构造函数不能有参数
6. 下列关于 this 指针的说法,正确的是( )
A. this 指针只能在静态成员函数中使用
B. this 指针指向当前对象
C. this 指针可以改变为指向其他对象
D. 每个类只有一个 this 指针
7. 关于静态数据成员,下列说法正确的是( )
A. 每个对象各自保存一份静态数据成员
B. 静态数据成员属于类,通常需要在类外定义
C. 静态数据成员只能是 private
D. 静态数据成员不能被成员函数访问

## PDF 第 2 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0002-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 2 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=2
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

8. 重载运算符函数 operator+ 作为成员函数时,表达式 a+b 等价于( )
A. operator+(a,b)
B. a.operator+(b)
C. b.operator+(a)
D. operator+(b,a)
9. 在公有继承 class B: public A 中,基类 A 的 public 成员在 B 中成为( )成员。
A. public
B. protected
C. private
D. 不可访问
10. 若基类 A 和派生类 B 都定义了同名普通成员函数 f(),且有 A *p = new B;,调用 p->f() 时(未使用 virtual),
执行的是( )
A. A::f()
B. B::f()
C. 两个函数都执行
D. 编译错误
二、程序改错(本题共 16 分)
11. (8分)下面程序希望统计创建了多少本 Book 对象,并输出书名和对象个数。请找出其中 4 个错误,指出错误
所在行号,并给出修改意⻅。
[1] #include <iostream>
[2] using namespace std;
[3] class Book {
[4] char title[30];
[5] public:
[6] static int count;
[7] Book(char t[]) {
[8] title = t;
[9] count++;
[10] }
[11] void show() { cout << title << endl; }
[12] static int getCount() { return count; }
[13] }
[14] int main() {
[15] Book b1("C++");
[16] Book b2("Data");
[17] b1.show;
[18] cout << Book::count << endl;
[19] return 0;
[20] }
答:____________________________________________________________


## PDF 第 2 页 · 片段 2
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0002-c02
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 2 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=2
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

count << endl;
[19] return 0;
[20] }
答:____________________________________________________________
答:____________________________________________________________
答:____________________________________________________________
答:____________________________________________________________
12. (8分)下面程序希望用单链表保存若干整数,并输出所有结点。请找出其中 4 个错误,指出错误所在行号,
并给出修改意⻅。
[1] #include <iostream>
[2] using namespace std;
[3] class Node {
[4] int data;
[5] public:
[6] Node *next;
[7] Node(int d) { data = d; next = nullptr; }
[8] int getData() { return data; }
[9] };
[10] class List {
[11] Node *head;
[12] public:
[13] List() { head = nullptr; }

## PDF 第 3 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0003-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 3 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=3
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

[14] void pushFront(int x) {
[15] Node *p = new Node(x);
[16] p.next = head;
[17] head = p;
[18] }
[19] void print() {
[20] Node *p = head;
[21] while(p != nullptr) {
[22] cout << p->data << " ";
[23] p = p->next;
[24] }
[25] cout << endl;
[26] }
[27] void clear() {
[28] Node *p = head;
[29] while(p != nullptr) {
[30] Node *q = p->next;
[31] delete [] p;
[32] p = q;
[33] }
[34] head = nullptr;
[35] }
[36] };
[37] int main() {
[38] List list();
[39] for(int i=1; i<=3; i++)
[40] list.pushFront(i*10);
[41] list.print();
[42] list.clear();
[43] return 0;
[44] }
答:____________________________________________________________
答:____________________________________________________________
答:____________________________________________________________
答:____________________________________________________________
三、程序写结果(本题共 24 分)
13. (6分)写出下列程序的运行结果。
#include <iostream>
using namespace std;
class Counter {
static int num;
int id;
public:


## PDF 第 3 页 · 片段 2
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0003-c02
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 3 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=3
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

下列程序的运行结果。
#include <iostream>
using namespace std;
class Counter {
static int num;
int id;
public:
Counter() { id = ++num; cout << "C" << id << " "; }
~Counter() { cout << "D" << id << " "; }
};
int Counter::num = 0;
int main() {
Counter a;
{ Counter b; }
Counter c;
return 0;
}
答:____________________________________________________________
14. (6分)写出下列程序的运行结果。
#include <iostream>
using namespace std;
class A {
public:
A() { cout << "A "; }
~A() { cout << "~A "; }
};
class B : public A {
public:
B() { cout << "B "; }
~B() { cout << "~B "; }
};
int main() {

## PDF 第 4 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0004-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 4 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=4
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

B obj;
return 0;
}
答:____________________________________________________________
15. (6分)写出下列程序的运行结果。
#include <iostream>
using namespace std;
class Point {
int x, y;
public:
Point(int a=0, int b=0) { x=a; y=b; }
Point operator+(Point p) { return Point(x+p.x, y+p.y); }
void print() { cout << "(" << x << "," << y << ")" << endl; }
};
int main() {
Point p1(1,2), p2(3,4);
Point p3 = p1 + p2;
p3.print();
return 0;
}
答:____________________________________________________________
16. (6分)写出下列程序的运行结果。
#include <iostream>
using namespace std;
class Base {
public:
virtual void fun() { cout << "Base" << endl; }
};
class Derived : public Base {
public:
void fun() { cout << "Derived" << endl; }
};
int main() {
Base *p;
Derived d;
p = &d;
p->fun();
return 0;
}
答:____________________________________________________________
四、程序填空(本题共 20 分)
每空 2 分。请把答案填写在答题纸的相应编号处。
17. (10分)下面程序已经建立了一个不带头结点的单链表,请补全 traverse 函数,输出所有结点并求数据之和。
#include <iostream>


## PDF 第 4 页 · 片段 2
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0004-c02
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 4 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=4
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

分。请把答案填写在答题纸的相应编号处。
17. (10分)下面程序已经建立了一个不带头结点的单链表,请补全 traverse 函数,输出所有结点并求数据之和。
#include <iostream>
using namespace std;
struct Node {
int data;
Node *next;
};
void traverse(Node *head) {
Node *p = ______(1)______;
int sum = 0;
while(______(2)______) {
cout << p->data << " ";
sum += ______(3)______;
p = ______(4)______;
}
cout << endl << "sum=" << ______(5)______ << endl;
}
int main() {
Node n3 = {30, nullptr};
Node n2 = {20, &n3};
Node n1 = {10, &n2};
traverse(&n1);
return 0;
}
(1):____________________________________________________________

## PDF 第 5 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0005-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 5 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=5
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

(2):____________________________________________________________
(3):____________________________________________________________
(4):____________________________________________________________
(5):____________________________________________________________
18. (10分)下面程序定义了一个 Student 类和一个学生数组,统计成绩不低于 60 分的学生人数,并输出平均成
绩。请补全程序。
#include <iostream>
#include <iomanip>
using namespace std;
class Student {
private:
int id;
double score;
public:
Student(int i=0, double s=0) : ______(6)______ {}
double getScore() { return score; }
void setScore(double s) { ______(7)______; }
};
int main() {
Student a[5] = { Student(1,72), Student(2,58),
Student(3,90), Student(4,66),
Student(5,84) };
int pass = 0;
double sum = 0;
for(int i=0; i<5; i++) {
sum += ______(8)______;
if(a[i].getScore() >= 60)
______(9)______;
}
cout << pass << endl;
cout << fixed << setprecision(1) << ______(10)______ << endl;
return 0;
}


## PDF 第 5 页 · 片段 2
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0005-c02
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 5 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=5
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

;
}
cout << pass << endl;
cout << fixed << setprecision(1) << ______(10)______ << endl;
return 0;
}
(6):____________________________________________________________
(7):____________________________________________________________
(8):____________________________________________________________
(9):____________________________________________________________
(10):____________________________________________________________

## PDF 第 6 页 · 片段 1
material_id: study-s2-programming-69542effd80181aa
version: sha256:69542effd80181aaad6fb69c491380107655b11c28e7e2a01f54cbbfe83f39b7
course_id: y1-s2-programming
chunk_id: study-s2-programming-69542effd80181aa-p0006-c01
source_label: 用户提供的大一期末复习资料；第三方来源/年份按原文件名保留，未核验官方真题身份
page_label: PDF 第 6 页
source_excerpt_ref: knowledge/study/sources/year1/pdf/study-s2-programming-69542effd80181aa.pdf#page=6
extraction_method: pdfplumber_visible_bbox
quality_warning: 未逐项人工校对；公式/代码/手写/图表需对照原 PDF，OCR 仅作为定位线索。

五、程序设计(本题共 20 分)
19. (10分)设计一个基类 Person,包含姓名 name 和年龄 age 两个数据成员;再设计公有派生类 Student,增加学
号 id 和成绩 score 两个数据成员。要求:Person 类有构造函数和 show 函数;Student 类有构造函数,并在构造函数
中调用基类构造函数;Student 类重新定义 show 函数,输出姓名、年龄、学号和成绩;在 main 函数中创建 Student
对象并调用 show 函数。
20. (10分)某城市正在建设一个“校园模拟选举与数据公示平台”,平台每天要接收多个候选人的票数,并计算每
位候选人的得票率,便于学生理解公开投票统计流程。真实系统会涉及身份核验、异常票处理、网络传输和数据
库存储等复杂内容,但本题只要求完成相关的类与对象设计。请设计一个 Candidate 类,至少包含候选人姓名
name、编号 id 和票数 votes 等私有数据成员;提供构造函数、addVotes 函数、getVotes 函数和 show 函数。show 函
数接收总票数 total,输出候选人基本信息和得票率。在 main 函数中定义 3 个候选人对象,给每人增加若干票数,
计算总票数并输出统计结果。
