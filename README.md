# 自有主机 Xray 反向代理出口

在有 Python 3 和兼容 Xray 二进制的出口主机运行。每次选一个节点，复制 params.example.json 为 params.json，限制为 600 权限，填写该节点模板引用的字段。参数须与对端配置匹配。已有节点迁移时先停旧实例，新增独立节点时先在对端分配对应身份。

    python3 render.py 2h params.json config.json
    xray run -test -config config.json
    xray run -config config.json

2h 和 6h 使用 TCP + REALITY，分别使用 XRAY_ID2、XRAY_ID1。c2 和 c6 使用 XHTTP + TLS，各自使用 C2_ 或 C6_ 开头的参数。旧工作流的 XRAY_VERSION 用于选择二进制，安装时核对版本。输出文件必须是新路径。参数和生成配置仅保存在实例本地。
