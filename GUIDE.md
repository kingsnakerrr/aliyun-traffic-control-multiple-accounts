# 阿里云 CDT 多账号机器人：配置、权限、换 IP 操作教程

适用范围：本仓库的 `cdt` 菜单和 Telegram 机器人。本文可在 GitHub 阅读，也可向机器人私聊发送 `/guide` 下载。界面名称可能随阿里云、Cloudflare 更新而变化，找不到按钮时优先用控制台搜索框搜索功能名。

> **先保护密钥**：AccessKey Secret、Cloudflare API Token、Telegram Bot Token 不要截图、发群、提交 GitHub。AccessKey Secret 只在创建时显示一次，旧 Secret 无法找回。若完整密钥曾出现在截图或聊天中，应立即在阿里云 RAM 控制台轮换或禁用/删除旧密钥，再把新密钥填入服务器。本教程不包含任何真实密钥。

## 1. 先看清三个“区域”和两个密钥

| 名称 | 填什么 | 示例 |
| --- | --- | --- |
| ECS 区域 ID | 实例真实所在地域；在 ECS 实例详情查看 | 香港 `cn-hongkong`，日本东京 `ap-northeast-1` |
| 账单接口区域 | 账单 API 接入区域，与 ECS 所在地无关 | 国内版通常 `cn-hangzhou`；国际版通常 `ap-southeast-1` |
| Cloudflare 区域 ID / Zone ID | 解析主域名的区域 ID，不是 Cloudflare 账户 ID | `example.com` 的概览页 API 区域内复制 |
| 阿里云 AccessKey ID + Secret | 调阿里云 ECS、CDT、账单、EIP API | 每个阿里云账号各自的 RAM 用户密钥 |
| Cloudflare API Token | 改 DNS A 记录 | 只授予目标 Zone 的 DNS 编辑权限 |

例如机器域名是 `abc.example.com`，Cloudflare Token 的资源范围选择 `example.com`，机器人中的完整域名填 `abc.example.com`，Zone ID 复制 `example.com` 的区域 ID。不能选 `abc.example.com` 当 Zone，除非它本身已在 Cloudflare 单独托管为一个 Zone。

## 2. 在阿里云找到或创建 RAM 用户

1. 用**持有 ECS 的那一个阿里云主账号**登录 [RAM 控制台](https://ram.console.aliyun.com/)。两个阿里云主账号各管各的 RAM 用户与密钥，不能跨账号授权。
2. 左侧选择 **身份管理 → 用户**。若列表为空，说明该主账号还没有普通 RAM 用户；主账号本身不会显示在 RAM 用户列表里。
3. 可复用你刚创建的 RAM 用户，不必再创建一个；但必须使用**这个用户的 AccessKey**，给这个用户授权。不要勾选 `AliyunECSImageExportDefaultRole`、`AliyunECSImageImportDefaultRole` 之类的 RAM 角色作为授权主体，它们不是机器人使用的 RAM 用户。
4. 若需要新建，点 **创建用户**，取容易识别的名称，例如 `cdt-bot`，访问方式选**程序访问 / 使用永久 AccessKey**，不需要控制台登录。创建后保存一次性显示的 AccessKey ID 和 Secret。
5. 如果是通过 **快速开始 → 用于程序访问的超级用户** 创建，用户和 AccessKey 已经生成；该快速方式通常会给 `PowerUserAccess`，权限范围比机器人所需更大。确认机器人能使用后，建议改成下节的最小权限策略并移除不需要的宽权限。

**寻找已有 AccessKey**：进 **身份管理 → 用户 → 选择用户 → 认证管理/AccessKey**，可查看 AccessKey ID、状态和使用时间；**看不到原来的 Secret**。不知道 Secret 就创建新密钥并轮换，不要试图恢复。一个 RAM 用户最多两个 AccessKey。

**已经泄露密钥**：先新建第二把密钥，在 SSH 的 `cdt → 选择账号序号 → 8. 编辑这个账号` 更新 ID 与 Secret，验证 `/status`、`/traffic` 和 `/bill` 正常后禁用、删除旧密钥。若泄露的是高权限密钥，应尽快禁用，并检查操作审计、账单和资源异动。不要把新密钥发给机器人或贴在聊天里。

## 3. 给正确的 RAM 用户授权

1. 在 RAM 控制台左侧找 **权限管理 → 权限策略 → 创建权限策略**，切到 JSON 编辑器，粘贴下面策略，取名如 `CdtBotMinimal` 并保存。
2. 到 **权限管理 → 授权 → 新增授权**（或者进该 RAM 用户的权限页点授权）。资源范围选 **账号级别**，授权主体勾选**实际创建 AccessKey 的 RAM 用户**，策略选刚保存的自定义策略，确认新增授权。
3. 若想确认当前用的是哪个用户，在 RAM 用户详情的 AccessKey 列表中核对已配置的 AccessKey ID；不要通过猜测用户名来授权。`Forbidden.RAM` 时先查是不是授错了用户、用了另一主账号的密钥、或策略尚未生效。

下面列出当前脚本实际调用的动作。`Resource: "*"` 只开放列出的动作，但仍是该主账号内全部匹配资源；EIP 写入权限有费用和断网风险。懂 RAM 资源 ARN 后可按实例和地域进一步收窄，不要随意用 `AdministratorAccess`。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeInstances",
        "ecs:StartInstance",
        "ecs:StopInstance",
        "cdt:ListCdtInternetTraffic",
        "bssapi:QueryAccountBalance",
        "bssapi:QueryBillOverview",
        "vpc:DescribeEipAddresses",
        "vpc:AllocateEipAddress",
        "vpc:UnassociateEipAddress",
        "vpc:AssociateEipAddress",
        "vpc:ReleaseEipAddress"
      ],
      "Resource": "*"
    }
  ]
}
```

如果暂时只用状态/保活、不换 IP，可先移除 5 个 `vpc:` 动作。需要换 IP 再加。账单查询若平台提示 BSS 授权不足，可检查 `bssapi:QueryAccountBalance`、`bssapi:QueryBillOverview` 是否被接受，或参考阿里云 BSS 文档中的对应权限点 `bss:DescribeAcccount`（官方拼写就是三个 c）和 `bss:DescribeBillList`。权限不足时看报错中的 API 名称，对照策略改动；不要直接增加管理全部资源的权限。

`Forbidden.RAM User not authorized` 或 `vpc:DescribeEipAddresses` 报错：这是**阿里云**权限问题，不是 Cloudflare Token 问题。前述策略必须授权到机器人正在使用的 AccessKey 所属 RAM 用户。只给查询权限可通过预检，但申请/解绑/绑定/释放仍可能失败，因此要确认全部 5 个 `vpc:` 动作。

## 4. 在 Cloudflare 取得 Zone ID 和 API Token

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)，选托管主域名，例如 `example.com`。
2. 进该域名的 **概览 / Overview**，向下找到 **API** 区块，复制 **区域 ID / Zone ID**。同一区块还显示**账户 ID / Account ID**，两者都是 32 位，**不能填错**。机器人会读取 Zone 名称并核对完整域名。
3. 在 Cloudflare 个人资料的 **API 令牌 / API Tokens → 创建令牌 / Create Token**，可从 `Edit zone DNS` 模板开始，或自行创建自定义令牌。**不要用 Global API Key，也不要填 Account ID 当令牌**。
4. 权限选 **区域 / Zone → DNS → 编辑 / Edit**；资源范围选 **包括 / Include → 特定区域 / Specific zone → `example.com`**。这表示允许修改 `example.com` Zone 内的 `abc.example.com` 等子域名。当前脚本调用读取 Zone、读取 DNS 记录、写 DNS 记录；Cloudflare API 文档允许 Zone 详情由 DNS Write 访问，DNS 编辑可用于 DNS 读取/写入。若你的令牌策略或控制台额外限制读取，可再加 **区域 / Zone → 区域 / Zone → 读取 / Read**，不要直接放大到所有 Zone。
5. 完成创建后复制一次性展示的 Token，妥善保管。若忘了或输错，用 Cloudflare 创建新 Token，并在 TG `/cfconfig` 中替换；旧 Token 不再需要时撤销。
6. 在 Cloudflare **DNS → 记录** 中为每台机器建立一条 A 记录，名称如 `abc`，内容填这台 ECS 当前直绑 EIP。记录在 CF 控制台可能显示 `abc`，机器人里填完整域名 `abc.example.com`。是否开启橙云代理按自己的业务决定；已有记录的代理设置会保留。**不要**让同一个域名对应两台机器。

## 5. SSH 安装、升级和修改阿里云账号

已有安装直接 SSH 登录服务器，运行 `cdt`，首页选 **x. 一键升级程序**，按提示输入 `yes`。升级会更新主程序、菜单、service 和本教程，不会覆盖 `accounts.json`、通知状态、日志或 venv。升级完成后机器人会重启，等几秒再试 `/guide`。

若旧版 `cdt` 菜单没有 `x`，先运行：

```bash
curl -fsSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/main/cdt -o /usr/local/bin/cdt
chmod +x /usr/local/bin/cdt
cdt
```

新增第二个阿里云账号：`cdt → a. 增加账号`。修改现有账号密钥、实例 ID、ECS 地域、账单接口区域或保活开关：`cdt → 输入账号序号 → 8. 编辑这个账号`。对没有改动的字段按回车保留旧值。配置保存在服务器 `/root/aliyun-traffic-control/accounts.json`；不要上传该文件或带有 Telegram 凭证的 `traffic_control.py` 到 GitHub。必要时可在 `cdt → t` 查看服务状态和日志。

报表里的 **CDT 流量阈值**是你在脚本中设置的停机线，不等于阿里云官方免费额度；费用和实际额度以当前阿里云控制台账单、产品规则为准。超过阈值时脚本会关机，保活不会强行拉起；月初满足流量低于阈值等条件后才会尝试开机。探针离线时先看 `/status` 的流量控制与实例状态、`cdt` 日志，不能仅凭探针断定是保活失效。

## 6. 在 TG 配置并验证每台机器的 Cloudflare

1. **私聊**机器人，发送 `/cfconfig`，选择账号。机器人只接受配置的管理员私聊。
2. 点 **修改域名**，填完整域名，例如 `abc.example.com`；点 **修改区域 ID**，填 `example.com` 概览页的 Zone ID；点 **更换 API 令牌**，填仅授权该 Zone DNS 编辑的 Token。每个阿里云账号都要配置对应的域名/Zone/Token；同一 Zone 下的两台机器可以使用同一个受限 Token，但域名必须不同。
3. 点 **验证配置**。它只查询 Zone 和 DNS，不会换 IP。验证通过再发送 `/changeip`。若填错，可随时再次 `/cfconfig` 修改任一项；输入到一半发送 `/cancel` 退出，不会被卡在循环。机器人会尝试删除含 Token 的 TG 消息；若删除失败，请自己删除并考虑换 Token。

## 7. 单账号或批量换 IP

发送 `/changeip`。点某个账号可单独换：尚缺 CF 配置时机器人会逐项询问，完成后再次验证并显示确认。点 **一键更换已配置启用账号**：机器人会对每个**启用**账号做只读预检，只把以下全部通过的账号放进确认清单：阿里云账号字段完整、CF Zone 与域名匹配、能查询当前直绑的普通按量 EIP、CF 中已有唯一 A 记录且记录内容等于旧 EIP。未配置、已禁用、DNS 不一致、EIP 不受支持或查询权限不足的账号会跳过并显示原因；**批量不会跳进配置问答，也不会替你创建缺失的 A 记录**。

确认前核对清单。只读预检**无法验证写权限、配额或新 EIP 的价格**，真正执行仍可能失败。换 IP 会先申请新 EIP，再解绑旧 EIP、绑定新 EIP、更新并回读 CF A 记录，最后释放旧 EIP；中间会短暂断网，可能产生额外费用。出现失败或超时，先查机器人报告的 EIP ID、阿里云控制台绑定状态和 Cloudflare 解析，**不要连续重复点击**。如果不是直绑 ECS EIP，而是固定公网 IP、辅助网卡 EIP、共享带宽或包年包月 EIP，当前机器人不会自动换。

## 8. 常见问题速查

| 现象 | 检查顺序 |
| --- | --- |
| 机器人通知正常，但换 IP 显示“无效” | Telegram 通知与阿里云/CF API 是不同凭证；先用 `/cfconfig` 验证 Zone/Token，再查阿里云 AccessKey、EIP 类型与 RAM 授权。 |
| Cloudflare `Zone ID` 校验失败 | 核对是否误填 **Account ID**；从目标域名概览页 API 区块重复制；确认 Token 资源范围包含该 Zone。 |
| CF 记录与旧 EIP 不一致 | 到 CF DNS 核对该机器的 A 记录是否指向当前直绑 EIP；不确认原因前不要强行换。 |
| `Forbidden.RAM` 或 `vpc:DescribeEipAddresses` | 查所用 AccessKey 属于哪个主账号、哪个 RAM 用户；给**那个用户**添加 EIP 权限策略。 |
| 第二个账号 RAM 用户列表为空 | 这个主账号尚未创建 RAM 用户；按第 2 节创建。另一个主账号的用户不会出现在这里。 |
| 创建了“用于程序访问的超级用户” | 可以复用这个 RAM 用户，但先安全轮换其密钥，再核对授权与机器人里配置的 ID/Secret。不要授权给镜像导入/导出角色。 |
| AccessKey Secret 找不到 | Secret 不可找回；创建新密钥并轮换，验证后删除旧密钥。 |
| `/guide` 显示文件未安装 | SSH 中 `cdt → x` 升级；或直接从本仓库下载 `GUIDE.md`。 |
| 机器离线/保活没有启动 | 查 `/status` 流量是否超阈值、实例是否 Stopped、账号和保活开关是否启用；查 `cdt → t` 的服务日志。 |

## 官方资料

- [阿里云：创建 RAM 用户](https://help.aliyun.com/zh/ram/user-guide/create-a-ram-user)
- [阿里云：给 RAM 用户授权](https://help.aliyun.com/zh/ram/user-guide/grant-permissions-to-the-ram-user)
- [阿里云：创建自定义权限策略](https://help.aliyun.com/zh/ram/create-a-custom-policy)
- [阿里云：EIP API 的 RAM 权限动作](https://help.aliyun.com/zh/eip/developer-reference/api-vpc-2016-04-28-ram-eips)
- [阿里云：账单 API 的 RAM 授权](https://help.aliyun.com/zh/user-center/developer-reference/api-calling-authorization)
- [阿里云：轮换 AccessKey](https://help.aliyun.com/zh/ram/user-guide/rotate-accesskey-pairs-of-ram-users)
- [阿里云：AccessKey 泄露处理](https://help.aliyun.com/zh/ram/user-guide/solution-to-accesskey-leakage)
- [Cloudflare：创建 API Token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Cloudflare：找到 Account ID 和 Zone ID](https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/)
- [Cloudflare：Zone 详情 API 权限](https://developers.cloudflare.com/api/resources/zones/methods/get/)
- [Cloudflare：DNS 读取和更新 API 权限](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/list/)
