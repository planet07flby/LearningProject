# QABook编译指南

**版本**: 2.1.0-alpha2
**更新日期**: 2025-10-25
**作者**: @yutiansut @quantaxis

---

## 📚 简介

本指南介绍如何在本地编译QABook PDF文档。QABook使用LaTeX编写，需要XeLaTeX编译器和中文字体支持。

---

## 🚀 快速开始

### 一键编译 (推荐)

```bash
# 进入项目根目录
cd /path/to/QUANTAXIS

# 进入qabook目录
cd qabook

# 使用编译脚本
bash build.sh
```

编译成功后会生成`quantaxis.pdf`文件。

---

## 📦 环境准备

### 安装LaTeX发行版

QABook需要完整的TeX Live发行版。

#### Linux (Ubuntu/Debian)

```bash
# 更新软件源
sudo apt-get update

# 完整安装 (推荐，~4GB)
sudo apt-get install -y texlive-full

# 或最小安装
sudo apt-get install -y \
    texlive-xetex \
    texlive-latex-extra \
    texlive-lang-chinese \
    texlive-fonts-recommended \
    texlive-science \
    fonts-wqy-microhei \
    fonts-wqy-zenhei
```

#### macOS

```bash
# 使用Homebrew安装MacTeX (~5GB)
brew install --cask mactex

# 或下载完整安装包
# https://www.tug.org/mactex/mactex-download.html
```

#### Windows

**方法1**: 安装TeX Live

1. 下载ISO镜像: https://www.tug.org/texlive/acquire-iso.html
2. 挂载ISO并运行`install-tl-windows.bat`
3. 选择"完整安装"
4. 等待安装完成（需要几个小时）

**方法2**: 安装MiKTeX (推荐Windows用户)

1. 下载: https://miktex.org/download
2. 运行安装程序
3. 选择"安装缺失的包"选项
4. 首次编译时会自动下载需要的包

### 验证安装

```bash
# 检查XeLaTeX版本
xelatex --version

# 应该看到类似输出:
# XeTeX 3.141592653-2.6-0.999995 (TeX Live 2024)
```

---

## 🔧 编译方法

### 方法1: 使用build.sh脚本 (推荐)

```bash
cd qabook/

# 编译PDF
bash build.sh

# 清理临时文件
bash build.sh clean

# 监控模式 (文件变更自动重新编译)
bash build.sh watch
```

**build.sh功能**:
- ✅ 自动检查XeLaTeX
- ✅ 编译三次确保目录和引用正确
- ✅ 自动清理临时文件
- ✅ 输出文件大小和编译结果

### 方法2: 手动编译

```bash
cd qabook/

# 第一次编译 (生成目录)
xelatex quantaxis.tex

# 第二次编译 (生成交叉引用)
xelatex quantaxis.tex

# 第三次编译 (确保所有引用正确)
xelatex quantaxis.tex

# 查看生成的PDF
ls -lh quantaxis.pdf
```

**为什么编译三次？**
- 第1次: 生成基本内容和辅助文件
- 第2次: 生成目录和交叉引用
- 第3次: 确保所有引用都正确

### 方法3: 使用latexmk (高级)

```bash
# 安装latexmk
sudo apt-get install latexmk

# 编译
latexmk -xelatex quantaxis.tex

# 持续监控模式
latexmk -pvc -xelatex quantaxis.tex
```

---

## 📁 文件说明

### 源文件

```
qabook/
├── quantaxis.tex      # LaTeX源文件
├── qalogo.png         # Logo图片
├── build.sh           # 编译脚本
└── README.md          # 完整使用指南
```

### 生成文件

编译后会生成以下文件：

```
qabook/
├── quantaxis.pdf      # 最终PDF (目标文件)
├── quantaxis.aux      # 辅助文件
├── quantaxis.log      # 编译日志
├── quantaxis.out      # 超链接信息
├── quantaxis.toc      # 目录信息
└── quantaxis.synctex.gz  # 同步信息
```

**临时文件说明**:
- `.aux`: LaTeX辅助信息
- `.log`: 编译日志，出错时查看
- `.out`: hyperref包的超链接信息
- `.toc`: 目录信息
- `.synctex.gz`: 编辑器和PDF同步

---

## 🛠️ 常见问题

### Q1: 编译失败 "! LaTeX Error: File 'xxx.sty' not found"

**原因**: 缺少LaTeX宏包

**解决**:

**Linux**:
```bash
# 安装扩展包
sudo apt-get install texlive-latex-extra

# 或安装完整版
sudo apt-get install texlive-full
```

**macOS**:
```bash
# 使用tlmgr安装缺失的包
sudo tlmgr install <package-name>
```

**Windows (MiKTeX)**:
- 打开MiKTeX Console
- 点击"Packages"
- 搜索并安装缺失的包

### Q2: 中文显示为方框或乱码

**原因**: 缺少中文字体

**解决**:

**Linux**:
```bash
# 安装中文字体
sudo apt-get install -y \
    texlive-lang-chinese \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-arphic-ukai \
    fonts-arphic-uming

# 刷新字体缓存
fc-cache -f -v
```

**macOS**:
系统已包含中文字体，无需额外安装。

**Windows**:
确保系统安装了中文字体（Windows默认已安装）。

### Q3: 编译速度很慢

**原因**: 文档较大，包含大量数学公式

**优化方法**:

1. **使用SSD硬盘**
2. **增加系统内存**
3. **开发时注释部分章节**:
   ```latex
   % \section{暂不需要的章节}
   % ...
   ```
4. **使用latexmk自动化工具**

### Q4: 如何查看编译错误？

```bash
# 查看完整日志
less quantaxis.log

# 或查看最后50行
tail -50 quantaxis.log

# 搜索错误信息
grep -i error quantaxis.log
```

**常见错误模式**:
- `! Undefined control sequence`: 未定义的命令
- `! Missing $ inserted`: 数学模式错误
- `! LaTeX Error: File 'xxx' not found`: 文件缺失

### Q5: PDF中的超链接不工作

**检查**: hyperref包的配置

在`quantaxis.tex`中确认:
```latex
\usepackage[colorlinks, linkcolor=black,
            anchorcolor=black, citecolor=black]{hyperref}
```

如果需要彩色链接:
```latex
\usepackage[colorlinks, linkcolor=blue,
            anchorcolor=blue, citecolor=green]{hyperref}
```

### Q6: 如何只编译部分章节？

**方法1**: 临时注释
```latex
% \section{不需要的章节}
% ...
```

**方法2**: 使用include (需要重构文档)
```latex
% 导言区
\includeonly{chapter1,chapter3}

% 正文
\include{chapter1}
\include{chapter2}  % 不会被编译
\include{chapter3}
```

---

## 📊 编译选项

### 编译模式

#### 草稿模式 (快速预览)

```bash
xelatex -interaction=nonstopmode "\def\isdraft{1}\input{quantaxis.tex}"
```

在文档中添加:
```latex
\ifdefined\isdraft
  \usepackage{draft}
  % 草稿模式设置
\fi
```

#### 最终模式 (高质量)

```bash
xelatex -interaction=nonstopmode quantaxis.tex
```

### 交互模式

- `nonstopmode`: 不停止，自动跳过错误
- `batchmode`: 批处理模式，不显示输出
- `scrollmode`: 滚动模式，遇到错误停止
- `errorstopmode`: 遇到错误立即停止

```bash
# 调试时使用，遇错即停
xelatex -interaction=errorstopmode quantaxis.tex
```

---

## 🎨 自定义编译

### 修改页面大小

在`quantaxis.tex`中修改:
```latex
% A4纸张 (默认)
\usepackage[a4paper, left=3.17cm, right=3.17cm,
            top=2.54cm, bottom=2.54cm]{geometry}

% 或使用Letter纸张
\usepackage[letterpaper, margin=1in]{geometry}
```

### 修改字体

```latex
% 在导言区添加
\setCJKmainfont{SimSun}        % 宋体
\setCJKsansfont{SimHei}        % 黑体
\setCJKmonofont{FangSong}      % 仿宋
```

### 添加水印

```latex
% 在导言区添加
\usepackage{draftwatermark}
\SetWatermarkText{草稿}
\SetWatermarkScale{3}
\SetWatermarkLightness{0.9}
```

---

## 🌐 CI/CD自动编译

QABook配置了GitHub Actions自动编译：

### 触发条件
- 推送到`master`分支
- `qabook/`目录有更新

### 工作流程
1. 安装TeX Live
2. 编译PDF (三次)
3. 上传到GitHub Releases

### 查看编译结果

访问[Actions页面](https://github.com/QUANTAXIS/QUANTAXIS/actions)查看编译状态。

### 下载自动编译的PDF

访问[Releases页面](https://github.com/QUANTAXIS/QUANTAXIS/releases)下载最新PDF。

---

## 🔗 相关资源

### 文档
- [QABook简介](introduction.md)
- [完整README](../../qabook/README.md)
- [在线文档](../README.md)

### 工具
- [Overleaf](https://www.overleaf.com/) - 在线LaTeX编辑器
- [TeXstudio](https://www.texstudio.org/) - LaTeX IDE
- [VS Code LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop)

### 学习资源
- [LaTeX入门](http://www.ctan.org/tex-archive/info/lshort/chinese/)
- [LaTeX Wikibook](https://en.wikibooks.org/wiki/LaTeX)
- [TeX Stack Exchange](https://tex.stackexchange.com/)

---

**维护者**: @yutiansut @quantaxis
**最后更新**: 2025-10-25

[← 上一页：QABook简介](introduction.md) | [返回文档中心](../README.md)
