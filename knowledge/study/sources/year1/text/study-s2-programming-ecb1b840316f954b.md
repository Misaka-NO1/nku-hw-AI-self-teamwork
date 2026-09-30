# 22笔试

> 原 PDF: knowledge/study/sources/year1/pdf/study-s2-programming-ecb1b840316f954b.pdf
> 页码指 PDF 文件第 N 页，不冒充印刷页码。公式及手写内容须对照原 PDF。

## PDF 第 1 页 · 片段 1

南开大学计算机大类本科生 2021—2022 学年第 2 学期
《高级语言程序设计 2-2》课程期末考试试卷(A 卷)
学院:__________专业:_________学号:________姓名:__________ 成绩:
得分
一 、单项选择(本题共 20 分,每小题 2 分)
请将答案填涂在答题纸的相应位置
1. 假设myClass是一个类,则执行”myClass a(2),b[2],*p[2];”语句时,
调用的myClass的构造函数的次数为( )
A. 3 B. 4 C. 5 D. 6
2. 关于类的成员函数,(cid:6655)述不正确的是( )
A. 静态成员函数不但可以访问类的所有public 数据成员,也可以访问类的所有
private数据成员
B. 成员函数可以重载
C. 类的成员函数既可以是内联函数,也可以不是
D. 类的友元函数虽然可以访问类的私有数据成员,但友元函数并不是类的成员函数
3. 如果++和*都是友元方式重载的运算符,则表达式++i*k可以表示为( )
A. operator*(i.operator++(),k)
B. operator*(operator++(i),k)
C. i.operator++().operator*(k)
D. k.operator*(operator++(i))
4. 对于只在表的首、尾两端进行插入操作的线性表,宜采用的存储结构为( )
A. 顺序表(用数组存储的线性表)
B. 用头指针表示的单循环链表
C. 用尾指针表示的单循环链表
D. 单链表
第-1-页共14页

## PDF 第 2 页 · 片段 1

5. 下列关于类的继承与派生的(cid:6655)述中,正确的是( )
A. 公有继承中,对于基类中的所有成员,派生类的成员函数都可以直接访问
B. 派生类对象的地址可以赋值给指向基类的指针
C. 基类的友元同样是派生类的友元
D. 派生类隐式继承基类的构造函数和析构函数
6. 类B是类A的公有派生类,类A和类B中都定义了虚函数func( ),p是一个指
向类A对象的指针,则p->func( )将( )
A. 调用类A中的函数func();
B. 调用类B中的函数func()
C. 根据p所指的对象类型而确定调用类A或类B中的函数func()
D. 既调用类A中函数,也调用类B中函数
7. 有如下函数模板定义:
template<class T>
T func(T x,T y)
{ return x*x+y*y; }
在下列对func的调用中,错误的是( )。
A. func(3, 5.5);
B. func(3.0, 5.5);
C. func(3, 5);
D. func<int>(3, 5.5)
8. 类模板的模板参数可用做( )
A. 数据成员的类型
B. 成员函数的类型
C. 成员函数的参数类型
D. 以上都可以
9. 下列关于关于虚函数的(cid:6655)述中,正确的是( )
A. 虚函数是一个静态成员函数
B. 虚函数是一个非成员函数
C. 虚函数是静态联编的一种实现方式
D. 派生类的虚函数与基类中对应的虚函数具有相同的参数个数和类型
10. 当使用ifstream 流类定义一个流对象并打开一个磁盘文件时,文件的默认打开
方式为( )
A. ios::in
B. ios::in |ios::binary
C. ios::out
D. ios::in | ios::app
第-2-页共14页

## PDF 第 3 页 · 片段 1

得分
二 、程序改错(本题共 16 分)
11. (8分)请找出程序中的4个语法错误,在答题纸上指出错误所在行,说明错误原
因或进行改正。
[1] class Node{
[2] public:
[3] int data;
[4] Node *next;
[5] Node(int i) {
[6] data = i;
[7] next = nullptr;
[8] }
[9] }
[10] class List {
[11] private:
[12] Node *head;
[13] static int nodeNum;
[14] public:
[15] List()
[16] {
[17] head = new Node();
[18] }
[19] void Insert(int k, int data);
[20] };
[21] List::nodeNum = 0;
[22] void Insert(int k, int data) {
[23] Node *newNode = new Node(data);
[24] Node *p = head;
[25] for(int i = 1; i < k+1; i ++)
[26] p = p->next;
[27] newNode->next = p;
[28] p->next = newNode;
[29] }
第-3-页共14页

## PDF 第 4 页 · 片段 1

12. (8分)请找出程序中的4个语法错误,在答题纸上指出错误所在行,说明错误原
因或进行改正。
[1] #include <iostream>
[2] using namespace std;
[3] class A {
[4] protected:
[5] int x;
[6] public:
[7] A(int a) :x(a){}
[8] void f() { cout << "A" << endl; }
[9] };
[10] class B :public A {
[11] using A::A(int a);
[12] public:
[13] int y;
[14] B(int a, int b) :A() { y = b; }
[15] void f(int a) { cout << "B" << endl; }
[16] void showall() {
[17] cout << "x: " << x << endl;
[18] cout << "y " << y << endl;
[19] }
[20] int getx() {
[21] return x;
[22] }
[23] };
[24] int main() {
[25] B b1(10,20);
[26] cout << "x: " << b1.x << endl;
[27] A* a = &b1;
[28] a->f(10);
[29] A* a2 = new B(30,40);
[30] a2->f();
[31] }
第-4-页共14页

## PDF 第 5 页 · 片段 1

得分
三 、读程序写结果(本题共 24 分)
13. (6分)请在答题纸上写出以下程序在Visual C++.Net环境下的运行结果。
#include<iostream>
using namespace std;
class Student
{
char *name;
int age;
float score;
static int num;
static float total;
public:
Student(char *,int,float);
void say() ;
static float getAverage();
};
int Student::num=0;
float Student::total=0;
Student::Student(char *name,int age,float score)
{
this->name=name;
this->age=age;
this->score=score;
num++;
total+=score;
}
void Student::say()
{cout<<name<<"的年龄是"<<age<<",成绩是"<<score<<"(当前共"<<num<<"
名学生) "<<endl;}
float Student::getAverage()
{ return total/num; }
int main()
{
(new Student("小明",15,90))->say();
(new Student("李磊",16,80))->say();
(new Student("张华",16,90))->say();
第-5-页共14页

## PDF 第 6 页 · 片段 1

(new Student("王康",14,60))->say();
cout<<"平均成绩为"<<Student::getAverage()<<endl;
return 0;
}
14. (6分)请在答题纸上写出以下程序在Visual C++.Net环境下的运行结果。
#include<iostream>
#include<cstring>
#include<stack>
using namespace std;
stack<int> s;
int main()
{
int n=10;
while(n)
{
s.push(n%2);
n /= 2;
}
while(s.size())
{
cout<<s.top();
s.pop();
}
return 0;
}
15. (6分)请在答题纸上写出以下程序在Visual C++.Net环境下的运行结果。
#include<iostream>
using namespace std;
class BaseClass
{
public:
BaseClass() {
cout << "Construction of Base Class" << endl;
}
void Fun1() {
cout << "Fun1() in BaseClass is called!" << endl;
第-6-页共14页

## PDF 第 7 页 · 片段 1

↑
}
virtual void Fun2() {
cout << "Fun2() in BaseClass is called!" << endl;
}
};
class DerivedClass : public BaseClass
{
public:
DerivedClass() { cout << "Construction of Derived Class" <<
endl; }
void Fun1() { cout << "Fun1() in DerivedClass is called!" <<
endl; }
void Fun2() { cout << "Fun2() in DerivedClass is called!" <<
endl; }
};
int main()
{
DerivedClass d;
BaseClass* pb = &d;
pb->Fun1();
pb->Fun2();
return 0;
}
16. (6分)请在答题纸上写出以下程序在Visual C++.Net环境下的运行结果。
#include<iostream>
#include<string>
using namespace std;
class Animal
{
public:
string name;
Animal(string n) :name(n) {
age = 10; cout << "Animal(string n) called" << endl;
}
Animal(string n, int a) :name(n), age(a) {
cout << "Animal(string n,int a) called" << endl;
}
Animal() {
name = "anonymity";age = 0; cout << "Animal() called" <<
endl;
}
~Animal() { cout << "Animal is destructing" << endl; }
第-7-页共14页

## PDF 第 8 页 · 片段 1

void print() {
cout << "name: " << name << endl;
cout << "age: " << age << endl;
}
protected:
int age;
};
class Cat :public Animal
{
public:
Animal animal;
Cat(string name,string _hair) :Animal(name),hair(_hair)
{
cout << "Cat(string name,string _hair) called" << endl;
}
Cat(string name):animal(name)
{
cout << "Cat(string name) called" << endl;
}
Cat(){ hair = "short";cout << "Cat() called" << endl; }
~Cat() { cout << "Cat is destructing" << endl; }
void print()
{
cout << "hair: " << hair << endl;
}
protected:
string hair;
};
int main()
{
Cat p1("cat","short");
p1.print();
Animal* p2 = new Animal("dog", 10);
p2 = &p1;
p2->print();
return 0;
}
第-8-页共14页

## PDF 第 9 页 · 片段 1

得分
四 、程序填空(本题共 20 分,每空 2 分)
17.将一条链表上相邻的两个结点合并成一个结点,即将第1个结点与第2个结点合
并,将第3个结点与第4个结点合并,......,如果链表上结点个数为奇数,则最后
一个结点不合并,直接作为合并后链表上的最后一个结点。合并2个结点的含义
是:将两个结点的数据成员data值相加。链表结点的数据结构为:
struct node{
int data;
struct node* next;
};
以下函数的参数h指向待合并链表的首结点,请完善该函数,并填写在答题纸的
相应编号处。
void merge(node *h)
{
node *p1, *p2;
if(h == NULL)
return;
p1 = h;
p2 = _____(1)_______;
while(p2)
{
p1->data += p2->data;
p1->next = p2->next;
_____(2)_______;
p1=p1->next;
if(p1 && p1->next)
p2 = p1->next;
else
p2 = ______(3)_______;
}
}
18.以下程序定义了一个分数类Rational,分子为nume,分母为deno。在类中重
载了分数的+和-运算。请完善该程序,并填写在答题纸的相应编号处。
#include<iostream>
第-9-页共14页

## PDF 第 10 页 · 片段 1

class Rational
{
int nume,deno;
public:
Rational(int x=0,int y=1){nume=x;deno=y;}
void print();
_________(1)_________
_________(2)_________
};
Rational Rational::operator+(Rational a)
{
Rational r;
r.deno=a.deno*deno;
r.nume=a.nume*deno+a.deno*nume;
return r;
}
Rational operator-(Rational a,Rational b)
{
Rational r;
r.deno=a.deno*b.deno;
r.nume=a.nume*b.deno-a.deno*b.nume;
return r;
}
19. 以下程序定义了一个名为circle的类,用于表示一个圆形,该类的属性r表示
圆的半径,area函数用于计算圆的面积。cylinder类为circle类派生出的
圆柱体类,用于表示一个圆柱体,其中属性h表示圆柱体的高,基类circle表
示底圆,area函数用于计算圆柱体的面积。请完善该程序,并填写在答题纸的相
应编号处。
#include<iostream>
using namespace std;
const double Pi = 3.14;
class circle {
public:
circle(double R);
double area()
{
return Pi*r*r;
}
protected:
第-10-页共14页

## PDF 第 11 页 · 片段 1

double r;
};
________(1)_______{
r = R;
}
class cylinder :public circle
{
protected:
double h;
public:
_________(2)_________{};
double area()
{
return _______(3)________;
}
};
void main() {
cylinder c(1,2);
cout << "The area of the cylinder c is "<< c.area()<< endl;
}
20. 下列程序将结构体变量t中的内容写入date.txt文件。请完善该程序,并填写
在答题纸的相应编号处。
#include <fstream.h>
struct date
{
int year,month,day;
};
int main()
{
date t={2002,2,12};
______(1)______;
if (!outdate)
{
cerr << "\n 文件不能打开" << endl ;
return;
}
______(2)_______;
}
第-11-页共14页

## PDF 第 12 页 · 片段 1

得分
五 、程序设计(本题共 20 分)
21. (10分)
去除一个已有的C++源程序文件中的所有的for语句。要求:
(1)在程序中由用户输入所要处理的cpp文件的文件名。
(2)如果该文件不存在返回一个(cid:6656)示信息
(3)去除程序中所有for语句后,得到的新程序存储到一个新文件中,新文件的文
件名是new+源文件名,例如原文件名是CPPfile.cpp,新文件是newCPPfile,cpp。
22. (10分)
为了遏制大型互联网平台利用行业优势地位,进行大数据杀熟、算法歧视、诱导
沉迷等不当行为,2022年3月1日《互联网信息服务算法推荐管理规定》开始施行,
《规定》明确,算法推荐服务(cid:6656)供者应当通过互联网信息服务算法备案系统填报服务
(cid:6656)供者名称、服务形式、应用领域、算法类型等备案信息。2022年8月,国内主流互
联网服务(cid:6656)供商,包括抖音、腾讯、阿里、网易、微博等都将自己的核心推荐算法做
了备案。下面是来自抖音的推荐算法备案信息:
算法运行机制:抖音个性化推送算法主要是基于用户历史的点击、时长、点赞、
评论、分享、转发、不喜欢等行为数据,通过深度学习技术框架建立模型,预估用户
对某个内容产生互动的概率,针对预估内容使用排序、打散、干预等机制和策略后,
再向用户进行推荐。用户行为参考<用户,内容,互动>三个维度作为样本进入机器学
习模型里训练,训练的结果用于更新用户模型和推荐新的内容。为了避免“信息茧房”
问题的出现,抖音个性化推荐算法专门设计了“兴趣探索”机制。一方面每次推荐都
会选择用户过去不常观看的内容类目进行一定比例的推荐。另一方面每次获取推荐内
容的过程中会特别增加一条随机内容来保障用户可见内容的多样性。
以上是题目背景,以下是题目要求。
假设名为User_Video的类记录某个用户对某个视频的属性,User_Video至少
包括以下私有数据成员,例如,用户ID(User_ID)、视频ID(Video_ID)、是否点
击、观看时长、是否点赞、是否评论、是否分享、是否转发、是否喜欢等。假设现在
有100个用户,100个视频。有一个数组,long order[100][100]记录了基于抖


## PDF 第 12 页 · 片段 2

Video_ID)、是否点
击、观看时长、是否点赞、是否评论、是否分享、是否转发、是否喜欢等。假设现在
有100个用户,100个视频。有一个数组,long order[100][100]记录了基于抖
音深度学习框架得到的针对每一个用户的推荐视频顺序。例如 order[0]记录对第0
号用户100个视频的推荐顺序,order[0][0]是推荐给0号用户的首个视频的ID,
依此类推。User_Video record[10000]记录每个用户针对每个视频的属性。第0
第-12-页共14页

## PDF 第 13 页 · 片段 1

号用户对100个视频的属性记录在record[0]-record[99],依此类推,题目要求:
(1)设计一个名为Exploration的函数,请自己设计实现一个合理的“兴趣探索”
机制。要求在order为每个用户推荐的前10个视频基础上,设计某种方法,插入3
个用户过去不常观看的视频和1条随机选择的视频,并与原有的6个视频一起重新生
成Top 10推荐视频。同时,简单解释你的方法的合理性。
(2)开放性问题:目前,为了实现流量变现,抖音开辟了直播带货、达人探店等商业
模式,请思考两方面问题:第一,作为一个用户,你如何发现抖音推荐算法出现了大
数据杀熟、算法歧视、诱导沉迷、卖流量等不当行为, 第二,如果你是抖音运营商,
如何在遵循法律和道德的前(cid:6656)下,实现自身的经济利益。
第-13-页共14页
