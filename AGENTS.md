# 资料栈 (Ziliaozhan) - AI Agent 项目指南

## 概述
资料栈 (ziliaozhan.vip) 是一个静态资料分享网站，提供高考真题、学习资料等 PDF 免费下载。
部署在阿里云青岛 ECS，Nginx + SSI 构建。

## 服务器
- IP: 47.94.216.51
- OS: Ubuntu 24.04
- 站点路径: /var/www/materials/
- SSH: root@47.94.216.51 (key-only)

## 技术栈
- Web Server: Nginx (HTTP 80→301→HTTPS 443, SSI, certbot SSL)
- SSL: Let's Encrypt (自动续期)
- 构建: Python (site_builder.py + gen_pages_v2.py)
- 验证: validate_smart.py (13项检查)
- GitHub: git@github.com:zjh418094680-afk/ziliaozhan.git (branch: master)

## 项目结构
```
/var/www/materials/
├── index.html              # 首页
├── site_builder.py         # 构建器
├── gen_pages_v2.py         # 子页面/文件列表生成
├── validate_smart.py       # 验证脚本
├── files.json              # 文件索引
├── sitemap.xml             # 站点地图
├── robots.txt              # 爬虫规则
├── inc/                    # SSI include
├── cat/                    # 分类页 (study, work, movie, game...)
├── study/gaokao/           # 高考真题 (按年/省/科)
├── study/kaoyan/           # 考研资料
└── history/                # 历史资料
```

## 强制约束
1. 零 ES6: 只用 var, 禁止 const/let/async/await/箭头函数/classList/fetch/template literal
2. 零 CSS var(): 颜色全部硬编码，暗色+亮色两套
3. 微信浏览器兼容: 必须支持 MicroMessenger 8.0.73
4. 全中文: 页面文本零英文
5. 配色: 主色 #3B82F6, 暗色背景 #0F172A→#1E293B→#334155
6. 主题切换: Nginx SSI 注入 class + JS cookie 切换
7. 事件委托用 .onclick, 禁止 HTML onclick 属性
8. CSS 不进 Python f-string, 用独立常量 + 拼接
9. 构建后必须 validate_smart.py 验证通过 (exit 0)

## 构建与验证
```bash
cd /var/www/materials
python3 site_builder.py      # 构建所有页面
# pre-commit hook 自动运行验证
```

## Nginx 关键配置
- /etc/nginx/sites-enabled/materials
- HTTP 自动跳 HTTPS (百度验证文件例外)
- 缓存 300s + Vary: Cookie
- /admin/ 路径: Basic Auth
- PDF inline 预览

## 部署流程
1. 修改代码/添加文件
2. 运行 site_builder.py 或 gen_pages_v2.py
3. 验证通过 (自动)
4. git commit + push
5. 服务器文件即生产环境

## 文件管理
- 新 PDF 放到 study/ 对应子目录
- gen_pages_v2.py 自动扫描生成文件列表
- files.json 自动更新
