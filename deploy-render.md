# 托管平台部署（可选）

无自有服务器时，可将本目录上传到自己的GitHub仓库，在支持Docker的托管平台创建Web Service，使用本目录Dockerfile。

环境变量：APP_HOST=0.0.0.0、APP_NO_BROWSER=1、APP_PUBLIC=1、APP_ALLOWED_ORIGINS=https://平台分配的域名、APP_DEMO_PASSWORD=至少16字符随机密码、APP_TASK_TIMEOUT=180。PORT使用平台注入的端口。健康检查路径/healthz。

先创建服务获得域名，再填写APP_ALLOWED_ORIGINS并重新部署。访问账号固定demo，密码是自己设置的评审密码。

使用支持长请求的实例，反向代理超时需超过180秒；建议2核CPU、2GB内存。免费服务可能休眠、限制计算时间，不适合现场稳定演示。平台方案尚未在真实账号部署验证。
