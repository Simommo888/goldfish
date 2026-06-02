# goldfish

`goldfish` 鏄竴涓潰鍚?Obsidian / Markdown 涓汉鐭ヨ瘑搴撶殑 AI 鎯呮姤 Agent銆傚畠姣忓ぉ鏀堕泦鍏紑 AI 鏂伴椈銆佸叧閿汉鐗╀笓涓氬姩鎬併€佽鏂囥€佸紑婧愰」鐩拰浜у搧鍔ㄦ€侊紝鍘婚噸銆佸垎绫汇€佽瘎鍒嗭紝骞剁敓鎴愪腑鏂?Markdown 鏃ユ姤锛涗篃鍙互鍩轰簬鏈€杩?7 澶╂棩鎶ョ敓鎴?AI 瓒嬪娍鍛ㄦ姤銆?

## 瀹冩瘡澶╁仛浠€涔?

1. 璇诲彇 `config/*.json`銆?
2. 鎶撳彇鍏紑 RSS / Atom 淇℃伅婧愩€?
3. 瀵规病鏈夌ǔ瀹?RSS 鐨勬潵婧愮敓鎴愨€滃緟浜哄伐鏌ョ湅鈥濇潯鐩€?
4. 璺熻釜 AI 鍏抽敭浜虹墿鐨勫叕寮€涓撲笟鏉ユ簮銆?
5. 杞婚噺瑙ｆ瀽 GitHub Trending锛屽け璐ユ椂浼橀泤闄嶇骇銆?
6. 鎶撳彇 arXiv RSS锛屽苟涓?Hugging Face Papers / Papers with Code 鐢熸垚浜哄伐鏌ョ湅鍏ュ彛銆?
7. 杩涜鍘婚噸銆佸垎绫汇€佸叧閿瘝璇勫垎銆?
8. 鏈?`DEEPSEEK_API_KEY` 鎴栧吋瀹?API Key 鏃惰皟鐢ㄧ湡瀹炲ぇ妯″瀷鐢熸垚鎽樿锛涙病鏈?Key 鏃朵娇鐢ㄨ鍒欐憳瑕併€?
9. 杈撳嚭 Markdown 鏃ユ姤銆佷汉鐗╁姩鎬併€丷aw JSON锛屽繀瑕佹椂鐢熸垚鍛ㄦ姤骞舵洿鏂?Dashboard銆?

## 鏈湴杩愯

鍦ㄧ煡璇嗗簱鏍圭洰褰曡繍琛岋細

```bash
python scripts/goldfish/goldfish.py
```

## Dry-run

Dry-run 涓嶅啓鍏?Obsidian 鏂囦欢锛屽苟涓旈粯璁や笉鑱旂綉锛岄€傚悎楠岃瘉閰嶇疆鍜屾祦绋嬶細

```bash
python scripts/goldfish/goldfish.py --dry-run --verbose
```

濡傛灉甯屾湜鐪熷疄鎶撳彇锛岃涓嶈鍔?`--dry-run`銆?

## 鍏抽棴 LLM

```bash
python scripts/goldfish/goldfish.py --no-llm
```

娌℃湁 `DEEPSEEK_API_KEY` 鎴栧吋瀹?API Key 鏃剁▼搴忎細鑷姩闄嶇骇涓鸿鍒欐憳瑕侊紝涓嶄細涓柇銆?

## 閰嶇疆澶фā鍨?API Key

鎺ㄨ崘浣跨敤 setup 鍚戝閰嶇疆妯″瀷鍜?API Key锛?

```powershell
goldfish setup
```

杩涘叆鍚庤緭鍏ワ細

```text
/model
```

鐒跺悗閫夋嫨 DeepSeek / OpenAI / OpenAI-compatible锛屽苟杈撳叆瀵瑰簲 API Key銆侹ey 浼氬啓鍏ョ敤鎴风骇鐜鍙橀噺锛屼笉浼氬啓鍏ラ」鐩厤缃€佹棩鎶ャ€丷aw JSON 鎴?Markdown銆?

## 缁存姢 sources.json

鏂囦欢浣嶇疆锛歚scripts/goldfish/config/sources.json`

姣忎釜鏉ユ簮鍖呭惈锛?

- `name`
- `category`
- `priority`
- `url`
- `rss_url`
- `enabled`
- `notes`

鏂板鏉ユ簮鏃跺繀椤诲啓鏄?`notes`锛岃鏄庝负浠€涔堝€煎緱鍏虫敞銆傛病鏈夌ǔ瀹?RSS 鏃舵妸 `rss_url` 鐣欑┖锛屽苟鍐欌€滃緟浜哄伐鏌ョ湅鈥濄€?

## 缁存姢 people.json

鏂囦欢浣嶇疆锛歚scripts/goldfish/config/people.json`

鏂板 AI 澶т浆鏃跺繀椤诲彧閰嶇疆鍏紑銆佷笓涓氥€佸彲寮曠敤鏉ユ簮锛屼緥濡傚崥瀹€佸叕鍙告柊闂汇€丟itHub銆丯ewsletter銆乊ouTube銆佸叕寮€婕旇椤点€備笉瑕佽拷韪浜虹敓娲汇€佸叓鍗︺€佺矇涓濅簤璁烘垨闇€瑕佺櫥褰曠殑鍐呭銆?

## 缁存姢 keywords.json

鏂囦欢浣嶇疆锛歚scripts/goldfish/config/keywords.json`

楂樹紭鍏堢骇鍏抽敭璇嶄細鎻愰珮璇勫垎锛岃礋闈㈠叧閿瘝浼氶檷浣庤瘎鍒嗐€備綘鐨勯噸鐐规柟鍚戝寘鎷?Agent銆丷AG銆丄I Coding銆丆odex銆丆laude Code銆丮CP銆並nowledge Base銆丄I 搴旂敤寮€鍙戝拰鎶€鏈彉鐜般€?

## 鏂板 AI 淇℃伅婧?

1. 鍦ㄥ悎閫傚垎绫讳笅鏂板 JSON 瀵硅薄銆?
2. 璁剧疆 `enabled=true`銆?
3. 鍐欐竻妤?`priority` 鍜?`notes`銆?
4. 鏈?RSS 灏卞～ `rss_url`锛屾病鏈夊氨鐣欑┖銆?
5. 杩愯 `--dry-run --verbose` 妫€鏌ラ厤缃€?

## 鏂板 AI 澶т浆

1. 鍦?`people.json` 鐨?`people` 鏁扮粍涓柊澧炲璞°€?
2. 鍙坊鍔犲叕寮€涓撲笟鏉ユ簮銆?
3. `reason` 蹇呴』璇存槑涓轰粈涔堝€煎緱杩借釜銆?
4. 鏃?RSS 鐨勬潵婧愬啓鈥滃緟浜哄伐鏌ョ湅鈥濄€?

## 鍏抽棴鏌愪釜鏉ユ簮

鎶婂搴旀潵婧愮殑 `enabled` 鏀逛负 `false`銆?

## 杈撳嚭浣嶇疆

- 鏃ユ姤锛歚04_Resources/AI-News/Daily/AI鎯呮姤鏃ユ姤-YYYY-MM-DD.md`
- AI 澶т浆鍔ㄦ€侊細`04_Resources/AI-News/People-Watch/AI澶т浆鍔ㄦ€?YYYY-MM-DD.md`
- 鍛ㄦ姤锛歚04_Resources/AI-News/Weekly/AI瓒嬪娍鍛ㄦ姤-YYYY-WW.md`
- Raw JSON锛歚04_Resources/AI-News/Raw/YYYY-MM-DD.json`

## 鏇存柊 Obsidian Dashboard

榛樿浼氭洿鏂?`01_Dashboard/Home.md`锛屽湪鏂囦欢鏈熬缁存姢涓€涓?`AI 鎯呮姤鏃ユ姤` 鍖哄煙锛屾渶澶氫繚鐣欐渶杩?7 鏉℃棩鎶ュ弻閾俱€備篃鍙互鎵嬪姩鎸囧畾锛?

```bash
python scripts/goldfish/goldfish.py --update-dashboard
```

## 鍚敤 GitHub Actions

宸ヤ綔娴佹枃浠讹細`.github/workflows/goldfish.yml`

鎶婄煡璇嗗簱鎺ㄥ埌 GitHub 鍚庯紝瀹冧細姣忓ぉ瀹氭椂杩愯锛屼篃鏀寔鎵嬪姩 `workflow_dispatch`銆傚鏋滀粨搴撴病鏈?`DEEPSEEK_API_KEY` Secret锛屽伐浣滄祦浼氳嚜鍔ㄧ敤 `--no-llm` 妯″紡杩愯銆傚伐浣滄祦浼氭彁浜ゆ棩鎶ャ€佸懆鎶ャ€丏ashboard锛屼互鍙婅嚜鍔ㄧ敓鎴愮殑姘镐箙绗旇 / 鍟嗕笟鎯虫硶 / Prompt / 椤圭洰鐏垫劅鑽夌銆?

## 閰嶇疆 GitHub Secrets

鍦?GitHub 浠撳簱璁剧疆涓柊澧?Secret锛?

- `DEEPSEEK_API_KEY`

涓嶈鎶?Key 鎻愪氦杩涗粨搴撱€?

## 鎶婃棩鎶ュ唴瀹规矇娣€杩涚煡璇嗗簱

寤鸿姣忓ぉ浠庢棩鎶ヤ腑鎸?3 鏉★細

- 闀挎湡瑙傜偣娌夋穩鍒?`05_Permanent-Notes`
- 鍟嗕笟鏈轰細娌夋穩鍒?`11_Business-Ideas`
- Prompt 娌夋穩鍒?`09_Prompts`
- Agent/RAG/AI Coding 鏂规硶娌夋穩鍒?`03_Areas`
- 鏆傛椂涓嶇煡閬撴斁鍝噷灏辨斁 `00_Inbox`

## 鍚庣画鎺ュ叆閫氱煡

`modules/notifier.py` 宸查鐣欙細

- email
- feishu
- wechat
- telegram

绗竴鐗堜笉鐪熸鍙戦€併€傚悗缁帴鍏ユ椂鎵€鏈?Token 浠嶅繀椤讳粠鐜鍙橀噺璇诲彇銆?

## 瀹夊叏杈圭晫

1. 鏈?Agent 鍙鐞嗗叕寮€淇℃伅銆?
2. 涓嶆姄鍙栫浜轰俊鎭€?
3. 涓嶈拷韪叓鍗︺€?
4. 涓嶇粫杩囩櫥褰曘€?
5. 涓嶇粫杩囧弽鐖€?
6. 涓嶄繚瀛?Cookie銆?
7. 涓嶆彁浜?API Key銆?
8. 涓嶇敓鎴愯櫄鍋囨潵婧愩€?
9. 涓嶇紪閫犱汉鐗╄鐐广€?
10. 鏃犳硶鎶撳彇鏃舵爣璁颁负鈥滃緟浜哄伐鏌ョ湅鈥濄€?

## 瀹夎渚濊禆

绗竴鐗堟湁鏍囧噯搴撻檷绾ф柟妗堬紱寤鸿瀹夎鍙€変緷璧栦互鎻愬崌 RSS 鍜?LLM 鏀寔锛?

```bash
pip install -r scripts/goldfish/requirements.txt
```

## goldfish 妯″紡

褰撳墠鐗堟湰宸茬粡涓嶅彧鏄棩鎶ヨ剼鏈紝鑰屾槸涓€涓瀭鐩存櫤鑳戒綋锛?

- 鎰熺煡锛氳鍙栧叕寮€ RSS銆佽鏂囥€丟itHub銆佷汉鐗╁姩鎬佸拰浜у搧婧愩€?
- 鍒ゆ柇锛氬幓閲嶃€佸垎绫汇€佽瘎鍒嗭紝骞剁粨鍚?Agent 璁板繂杩涜鍋忓ソ鍔犳潈銆?
- 琛ㄨ揪锛氱敓鎴?AI 鎯呮姤鏃ユ姤銆佷汉鐗╁姩鎬佸拰瓒嬪娍鍛ㄦ姤銆?
- 璁板繂锛氭妸杩愯鍘嗗彶銆佸亸濂戒富棰樸€侀珮浠峰€兼潵婧愪繚瀛樺埌 `scripts/goldfish/output_cache/agent_memory.json`锛屽苟鎶婅繍琛?瀵硅瘽鐘舵€佸啓鍏?SQLite銆?
- 琛屽姩锛氱敓鎴愭瘡鏃ョ煡璇嗘矇娣€寤鸿鎶ュ憡銆?
- 鍙嶉锛氱敓鎴愭瘡鏃ュ弽棣堣〃锛屼緵浣犲嬀閫夆€滃€煎緱娌夋穩 / 鍙仛椤圭洰 / 鏈夊晢涓氫环鍊?/ 澶氭帹鑽?/ 灏戞帹鑽愨€濄€?

鏂板杈撳嚭锛?

- 娌夋穩寤鸿锛歚04_Resources/AI-News/Reports/AI鎯呮姤娌夋穩寤鸿-YYYY-MM-DD.md`
- 鍙嶉琛細`04_Resources/AI-News/Reports/AI鎯呮姤鍙嶉-YYYY-MM-DD.md`
- Agent 璁板繂锛歚scripts/goldfish/output_cache/agent_memory.json`
- Agent 鐘舵€佸簱锛歚scripts/goldfish/output_cache/goldfish.db`

褰撳墠閰嶇疆鍏佽鑷姩鍒涘缓鍊欓€夎崏绋匡細

```json
"auto_create_knowledge_drafts": true
```

鍊欓€夎崏绋夸細鏍规嵁鍐呭绫诲瀷鍐欏叆锛?

- 姘镐箙绗旇锛歚05_Permanent-Notes/AI-Trends`
- 鍟嗕笟鎯虫硶锛歚11_Business-Ideas/AI-News-Inspirations`
- Prompt锛歚09_Prompts/AI-News`
- 椤圭洰鐏垫劅锛歚02_Projects/AI-News-Ideas`

鐩稿叧閰嶇疆鍦?`settings.json`锛?

- `enable_agent_memory`
- `enable_feedback_tracking`
- `generate_knowledge_report`
- `auto_create_knowledge_drafts`
- `knowledge_report_limit`
- `knowledge_min_score`
- `feedback_report_limit`

## CLI 浣跨敤鏂瑰紡

褰撳墠椤圭洰鏀寔涓ょ杩愯鏂瑰紡锛?

1. 鍏煎鏃ф柟寮忥細

```bash
python scripts/goldfish/goldfish.py --dry-run --verbose
```

2. CLI 鏂瑰紡锛?

```bash
python scripts/goldfish/cli.py dry-run --verbose
python scripts/goldfish/cli.py run --no-llm
python scripts/goldfish/cli.py weekly
python scripts/goldfish/cli.py config check
python scripts/goldfish/cli.py memory show
python scripts/goldfish/cli.py feedback list
python scripts/goldfish/cli.py history
python scripts/goldfish/cli.py search "MCP"
python scripts/goldfish/cli.py skills
python scripts/goldfish/cli.py sources health
python scripts/goldfish/cli.py tools
python scripts/goldfish/cli.py doctor
python scripts/goldfish/cli.py setup
```

濡傛灉甯屾湜瀹夎鎴愮湡姝ｇ殑鍛戒护锛?

```bash
pip install -e scripts/goldfish
```

瀹夎鍚庡彲浠ヤ娇鐢細

```bash
goldfish dry-run --verbose
goldfish run --no-llm
goldfish run --model gpt-4.1-mini
goldfish weekly
goldfish config check
goldfish memory show
goldfish history
goldfish search "AI Coding 鍟嗕笟鍖?
goldfish skills
goldfish sources health
goldfish tools
goldfish doctor
goldfish setup
```

CLI 鐨?`run`銆乣dry-run`銆乣weekly`銆乣doctor`銆乣history`銆乣tools` 绛夊懡浠ょ粺涓€璧?`ToolRegistry`锛屼笉鏄暎钀界殑鑴氭湰鍒嗘敮锛涜繖璁╁悗缁帴 TUI銆侀涔︺€佸井淇°€乀elegram 鎴?Web UI 鏃跺彲浠ュ鐢ㄥ悓涓€缁勬湰鍦拌兘鍔涖€?

## 鍙璇濇ā寮?

杩欎釜 Agent 涔熸敮鎸佺被浼?Hermes / OpenClaw / Codex / Claude Code 鐨勪氦浜掑紡 CLI銆傚畨瑁呭悗鐩存帴杈撳叆 `goldfish` 灏变細杩涘叆瀵硅瘽妯″紡锛?

```bash
goldfish
```

鏄惧紡鍐欐硶涔熶粛鐒跺彲鐢細

```bash
goldfish chat
```

杩涘叆鍚庤浣跨敤鑻辨枃 slash commands锛?

```text
/dry
/run
/weekly
/run --write-drafts
/config
/memory
/memory review
/memory context
/remember I prefer Agent commercialization
/forget Agent commercialization
/feedback
/doctor
/model
/base-url https://api.openai.com/v1
/llm
/no-llm
/tools
/history
/search MCP
/research MCP server best practices
/skills
exit
```

涔熷彲浠ュ崟鍙ヨ皟鐢細

```bash
goldfish chat --once "/config"
goldfish chat --once "/dry"
goldfish chat --no-llm --once "/memory"
goldfish chat --no-llm --once "/memory review"
goldfish chat --no-llm --once "/remember I care about MCP commercial opportunities --kind business"
```

Memory now follows an explicit Codex-like control model:

- `/remember <text>` saves a user-approved durable memory.
- `/forget <query>` removes matching memories by id or text.
- `/memory context` shows the compact context injected into LLM chat and agent loop.
- `/memory review` audits memory counts, stale candidates, and suggested updates.
- goldfish does not save API keys, cookies, or private credentials into memory.

瀵硅瘽鍘嗗彶浼氳褰曞埌锛?

```text
scripts/goldfish/output_cache/chat_history.jsonl
```

鎵ц杈圭晫锛?

- 鏄庣‘鐨勮繍琛屾剰鍥炬墠浼氭墽琛屾棩鎶ャ€佸懆鎶ャ€乨ry-run 绛夋湰鍦板姩浣溿€?
- 鏅€氶棶棰樺彧鍥炵瓟鐢ㄦ硶銆侀厤缃€佸伐浣滄祦鍜屽畨鍏ㄨ竟鐣屻€?
- 涓嶆墽琛屼换鎰?shell 鍛戒护銆?
- 鏃ュ父瀵硅瘽涓嶈鍙栨垨淇濆瓨 API Key锛涙ā鍨?Key 璇烽€氳繃 `goldfish setup` 閰嶇疆銆?
- 鏃?API Key 鏃讹紝瀵硅瘽灞傝嚜鍔ㄤ娇鐢ㄨ鍒欑悊瑙ｃ€?

## 鍐呴儴鏋舵瀯

褰撳墠浼樺厛鍙傝€冧簡 Hermes Agent 鐨勫嚑涓璁℃柟鍚戯細娓呮櫚鐨勫伐鍏疯竟鐣屻€丳rovider 鎶借薄銆佹湁鐘舵€佽繍琛屻€佸彲瀵硅瘽鍏ュ彛鍜岃瘖鏂兘鍔涖€?

- `modules/agent_kernel.py`锛氭牳蹇冭繍琛屽唴鏍革紝CLI銆佽亰澶┿€佸畾鏃朵换鍔￠兘璋冪敤杩欓噷銆?
- `modules/tool_registry.py`锛氭湰鍦板伐鍏锋敞鍐岃〃锛屽０鏄庡伐鍏锋槸鍚︿細鍐欐枃浠讹紝浠ュ強鍏佽鍐欏叆鐨勭煡璇嗗簱鍖哄煙銆?
- `modules/command_router.py`锛氭妸鑷劧璇█鎴?slash 鍛戒护璺敱鍒板伐鍏枫€?
- `modules/conversation_agent.py`锛氬彲瀵硅瘽 CLI锛屼細璇濆巻鍙插悓鏃跺啓鍏?JSONL 鍜?SQLite銆?
- `modules/providers/`锛歄penAI-compatible Provider 灞傦紝DeepSeek銆丱penAI 鎴栧叾浠栧吋瀹规湇鍔″彧鍦ㄨ繖閲屽鐞嗐€?
- `modules/state_store.py`锛歋QLite 鐘舵€佸簱锛岃褰曡繍琛屽巻鍙层€佹秷鎭拰鍊欓€夋礊瀵熴€?
- `modules/source_health.py`锛氭妸姣忔鎶撳彇缁撴灉杞崲鎴愭潵婧愬仴搴峰害璁板綍銆?
- `modules/search_engine.py`锛氭悳绱㈡棩鎶ャ€佽崏绋裤€佺姸鎬佸簱娲炲療鍜屼細璇濄€?
- `skills/*/SKILL.md`锛氳交閲忔妧鑳借鏄庯紝鍛婅瘔 Agent 濡備綍澶勭悊鐗瑰畾浠诲姟銆?

甯哥敤璇婃柇鍛戒护锛?

```bash
goldfish doctor
goldfish tools
goldfish history --limit 5
goldfish search "RAG 璇勬祴"
goldfish skills business-idea
goldfish sources health
goldfish chat --no-llm --once "/doctor"
```

## Skills 绯荤粺

杞婚噺鎶€鑳界洰褰曚綅浜庯細

```text
scripts/goldfish/skills/
```

Built-in information-retrieval skills:

- `retrieval-planning`: turn a vague research goal into a bounded tool plan.
- `query-expansion`: generate broad, narrow, source-specific, and local-search queries.
- `web-research`: collect public web evidence without login, cookies, or anti-scraping bypass.
- `internet-search`: choose Tavily, Jina, realtime news, Hacker News, GDELT, or DuckDuckGo for public web retrieval.
- `tavily-search`: use Tavily Search API when `TAVILY_API_KEY` is configured.
- `jina-search`: use Jina Search when `JINA_API_KEY` is configured.
- `source-evaluation`: judge source reliability, priority, freshness, and failure risk.
- `evidence-capture`: preserve claim-level evidence records with URLs and confidence.
- `fact-checking`: mark claims as verified, uncertain, unsupported, or out of scope.
- `answer-synthesis`: turn retrieved evidence into a concise source-backed answer.
- `knowledge-routing`: decide whether findings become permanent notes, prompts, project ideas, business ideas, reports, or Inbox items.
- `retrieval-review`: review retrieval quality and recommend follow-up searches or source changes.
- `external-cli-tools`: call allow-listed local CLI tools such as `rg`, `git`, `python`, `go`, `node`, and `chafa`.
- `source-curation`: maintain source lists and priorities.
- `trend-analysis`: turn repeated signals into trend judgments.
- `draft-writing`: write safe knowledge drafts from intelligence items.
- `business-idea`: extract users, pain points, MVPs, pricing, and validation steps.
- `weekly-review`: review the week and pick next focus areas.

鏌ョ湅鎶€鑳斤細

```bash
goldfish skills
goldfish skills retrieval-planning
goldfish skills web-research
goldfish skills business-idea
```

## External CLI Tools

goldfish can call local command-line tools through an allow-listed config file:

```text
scripts/goldfish/config/external_tools.json
```

This is intentionally not an unrestricted shell. Each external tool has a name, command template, timeout, output limit, runner, and allowed working directory. Secrets are redacted from output and long output is truncated.

List tools:

```powershell
goldfish external list
```

Run a tool:

```powershell
goldfish external run rg_search query=MCP path=scripts/goldfish
goldfish external run git_status
goldfish external run git_log limit=5
goldfish external run python_version
```

Preview without executing:

```powershell
goldfish external run rg_search query=Agent path=scripts/goldfish --dry-run
```

Inside chat:

```text
/external
/exec rg_search query=MCP path=scripts/goldfish
/exec git_status
```

To add a new CLI tool, edit `external_tools.json`. Prefer `runner: direct`. Use `runner: bash` only for reviewed commands, and keep destructive or mutating tools disabled until explicitly needed.

## 鎼滅储鍘嗗彶鎯呮姤

鎼滅储浼氬悓鏃舵煡 SQLite 鐘舵€佸簱銆佹棩鎶ャ€佸懆鎶ャ€佹矇娣€寤鸿銆佽嚜鍔ㄨ崏绋垮拰鑱婂ぉ璁板綍锛?

```bash
goldfish search "MCP"
goldfish search "AI Coding 鍟嗕笟鍖?
goldfish search "RAG 璇勬祴"
```

瀵硅瘽閲屼篃鍙互璇达細

```text
/search "AI Coding 鍟嗕笟鍖?
```

## Public Web Research

`search` searches local goldfish history and notes. `web` and `research` both use the unified `web_search` tool for public internet retrieval:

- `goldfish web ...` returns public search result links only.
- `goldfish research ...` uses the same tool in research mode: search, fetch accessible pages, synthesize, and optionally save a Markdown report.

```bash
goldfish web "MCP server best practices"
goldfish web "AI coding commercialization" --search-provider tavily
goldfish research "MCP server best practices"
goldfish research "AI coding commercialization" --limit 8 --fetch-limit 5
goldfish research "RAG evaluation methods" --no-llm
goldfish research "MCP server commercial opportunities" --search-provider tavily
goldfish research "AI coding agent market" --search-provider jina
```

鑱婂ぉ妯″紡閲屼篃鍙互浣跨敤锛?
```text
/web MCP server best practices
/research MCP server best practices
/research MCP server commercial opportunities --search-provider tavily
```

Search providers:

- `auto`: tries Tavily when `TAVILY_API_KEY` exists, then Jina when `JINA_API_KEY` exists, then DuckDuckGo fallback.
- `news`: optimized for latest/today/realtime queries. It tries configured Tavily/Jina first, then no-key Hacker News Algolia, GDELT DOC API, then DuckDuckGo.
- `tavily`: uses Tavily Search API. Configure `TAVILY_API_KEY`; optional `TAVILY_SEARCH_ENDPOINT`.
- `jina`: uses Jina Search. Configure `JINA_API_KEY`; optional `JINA_SEARCH_ENDPOINT`.
- `hackernews`: no-key Hacker News Algolia API, useful for latest developer/AI engineering links.
- `gdelt`: no-key GDELT DOC API, useful for global news article discovery.
- `duckduckgo`: no-key public HTML fallback.

Recommended setup flow:

```powershell
goldfish setup
```

Then enter:

```text
/search
```

Choose Tavily, Jina, News, Hacker News, GDELT, or DuckDuckGo. Tavily/Jina keys are saved to user-level environment variables only, not project files. On Windows, goldfish reads user-level environment variables directly, so a key saved with `goldfish setup` works even in an already-open terminal.

Non-interactive status:

```powershell
goldfish setup --once "/search list"
```

The default provider can also be set manually with:

```powershell
$env:GOLDFISH_SEARCH_PROVIDER="tavily"
```

Related skills:

```powershell
goldfish skills internet-search
goldfish skills tavily-search
goldfish skills jina-search
```

杈撳嚭榛樿淇濆瓨鍒帮細

```text
04_Resources/AI-News/Reports/WebResearch-YYYY-MM-DD-QUERY.md
```

瀹夊叏杈圭晫锛氬彧璁块棶鍏紑缃戦〉锛屼笉鐧诲綍銆佷笉淇濆瓨 Cookie銆佷笉缁曡繃鍙嶇埇銆佷笉鍋氭棤闄愰€掑綊鐖彇锛涙棤娉曡闂殑椤甸潰浼氳褰曞け璐ュ師鍥犮€?

## Local RAG Knowledge Base

goldfish can call a local RAG service as its Obsidian / long-term knowledge lookup layer. The default config is:

```text
scripts/goldfish/config/rag.json
```

Default endpoint:

```text
http://127.0.0.1:8020
```

Your current local RAG project can be started with:

```powershell
cd D:\github仓库\RAG-Knowledge-Base
python -m uvicorn main:app --reload --port 8020
```

Then use:

```powershell
goldfish rag status
goldfish rag ask "goldfish 项目是什么"
goldfish rag search "MCP"
```

Inside chat:

```text
/rag goldfish 项目是什么
/rag-search MCP
/rag-status
```

Natural-language requests that clearly mention the local knowledge base, Obsidian, saved notes, or RAG knowledge base can route to `rag_query` automatically:

```text
从我的知识库里查一下 goldfish 项目
query my knowledge base about MCP
```

Routing strategy:

- `rag_query`: answer from the configured local RAG service with source chunks.
- `rag_search`: return matching source chunks for manual inspection.
- `rag_status`: check health, stats, document count, chunk count, and config.
- `web_search`: still handles current/latest/public web information.
- `search`: remains the local goldfish history/chat/generated-note fallback.

Override the base URL without editing files:

```powershell
$env:GOLDFISH_RAG_BASE_URL="http://127.0.0.1:8020"
```

Safety boundary: goldfish only calls the configured local HTTP service. It does not read the RAG database directly, does not send API keys, does not save cookies, and degrades gracefully if the service is down.
## 璋冪敤鐪熷疄澶фā鍨?API

鐪熷疄妯″瀷 API 涓嶅啓鍏ラ厤缃枃浠躲€傛帹鑽愪娇鐢細

```powershell
goldfish setup
```

鍦?setup 涓緭鍏ワ細

```text
/model
```

閫夋嫨妯″瀷骞惰緭鍏?API Key 鍚庯紝杩愯锛?

```powershell
goldfish run
```

褰撳墠榛樿閰嶇疆宸茬粡浣跨敤 DeepSeek锛?

```json
{
  "llm_provider": "deepseek",
  "llm_model": "deepseek-v4-pro",
  "llm_base_url": "https://api.deepseek.com"
}
```

濡傛灉瑕佷复鏃惰鐩栨ā鍨嬶細

```powershell
goldfish run --provider deepseek --model deepseek-v4-pro --base-url https://api.deepseek.com
```

娌℃湁 API Key 鏃讹細

```powershell
goldfish run --no-llm
```

瀹夊叏瑙勫垯涓嶅彉锛氫笉瑕佹妸 API Key 鍐欏叆 `settings.json`銆佹棩鎶ャ€丷aw JSON 鎴栦换浣?Markdown銆?

濡傛灉浣犳洿鍠滄鎵嬪姩鐜鍙橀噺锛屼篃浠嶇劧鍙互浣跨敤锛?

```powershell
$env:DEEPSEEK_API_KEY="浣犵殑 DeepSeek API Key"
$env:AI_NEWS_LLM_MODEL="deepseek-v4-pro"
$env:AI_NEWS_LLM_BASE_URL="https://api.deepseek.com"
```

鏀寔鐨?Key 鐜鍙橀噺浼樺厛绾э細

1. `AI_NEWS_LLM_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `OPENAI_API_KEY`

濡傛灉浣犱箣鍚庢敼鐢ㄥ叾浠?OpenAI-compatible 鏈嶅姟锛屽彲浠ョ户缁敤锛?

```powershell
$env:AI_NEWS_LLM_API_KEY="浣犵殑鍏煎鎺ュ彛 Key"
goldfish run --provider openai --model "浣犵殑妯″瀷鍚? --base-url "https://浣犵殑鍏煎鎺ュ彛/v1"
```

## 鑷姩鐢熸垚鐭ヨ瘑鑽夌

褰撳墠宸茬粡鍏佽 Agent 榛樿鑷姩鐢熸垚鍊欓€夎崏绋匡細

```json
"auto_create_knowledge_drafts": true,
"draft_write_mode": "auto"
```

`draft_write_mode` 鏀寔锛?

- `off`锛氫笉鍐欒崏绋裤€?
- `suggest`锛氬彧鐢熸垚娌夋穩寤鸿鎶ュ憡锛屼笉鍐欏叆鑽夌鐩綍銆?
- `ask`锛氬璇濇ā寮忎笅绛夊緟纭锛涢潪浜や簰杩愯鍙爣璁伴渶瑕佺‘璁ゃ€?
- `auto`锛氳嚜鍔ㄥ啓鍏ュ€欓€夎崏绋裤€?

鍛戒护琛屽彲涓存椂瑕嗙洊锛?

```bash
goldfish run --draft-mode suggest
goldfish run --draft-mode ask
goldfish run --draft-mode off
goldfish run --write-drafts
```

姝ｅ紡杩愯 `goldfish run` 鍚庯紝闄や簡鏃ユ姤銆佷汉鐗╁姩鎬併€佹矇娣€寤鸿銆佸弽棣堣〃锛岃繕浼氭寜鍐呭绫诲瀷鍐欏€欓€夎崏绋匡細

- 姘镐箙绗旇锛歚05_Permanent-Notes/AI-Trends`
- 鍟嗕笟鎯虫硶锛歚11_Business-Ideas/AI-News-Inspirations`
- Prompt锛歚09_Prompts/AI-News`
- 椤圭洰鐏垫劅锛歚02_Projects/AI-News-Ideas`

鑽夌鏄€欓€夋潗鏂欙紝涓嶇瓑浜庢渶缁堢煡璇嗐€備綘浠嶇劧闇€瑕佹鏌ユ潵婧愩€佹敼鍐欐垚鑷繁鐨勫垽鏂紝鍐嶉摼鎺ュ埌鐩稿叧 MOC銆?

## CLI Pixel Theme

`goldfish` uses a terminal-native Bubble Tea / Lip Gloss startup screen that follows the supplied reference layout:

- `goldfish` starts directly in Python chat mode with a framed startup dashboard.
- The startup dashboard itself does not draw `gf >`; the real chat prompt is owned by the Python conversation loop.
- The default startup renderer is `go`, a Go Bubble Tea / Lip Gloss renderer built from `scripts/goldfish/tui/startup`.
- The Go renderer is JSON-driven. Edit `scripts/goldfish/tui/startup/layout.json` to move or resize the page regions.
- It uses Unicode box drawing, Unicode block characters, ANSI TrueColor, and real text.
- It does not render a screenshot, convert PNG to ANSI, rasterize text, use emoji-width glyphs, or use image protocols.
- Default JSON canvas: `120 columns x 40 rows`; rendered terminal footprint: `124 columns x 42 rows` with the outer frame.
- Recommended font: Cascadia Mono, Consolas, or JetBrains Mono.
- If the terminal is too small, goldfish shows a resize hint instead of rendering a broken layout.
- Non-interactive scripts and tests use the ANSI/Rich fallback so command output remains manageable.
- The dashboard keeps the reference layout: large left hero panel, right status/session column, three bottom panels, and command bar area.
- Chat slash commands remain English-only: `/research`, `/run`, `/dry`, `/doctor`, `/tools`, `/model`.
- ANSI colors are used when the terminal supports them. Set `NO_COLOR=1` or `GOLDFISH_NO_COLOR=1` to disable color.
- Force the Go renderer with `GOLDFISH_STARTUP_RENDERER=go`.
- Use a custom layout with `GOLDFISH_STARTUP_LAYOUT=C:\path\to\layout.json`, or preview directly with `goldfish-startup.exe --once --layout C:\path\to\layout.json`.
- Rebuild the renderer with `go build -o scripts/goldfish/output_cache/bin/goldfish-startup.exe ./scripts/goldfish/tui/startup`.
- Force the legacy fallback with `GOLDFISH_STARTUP_RENDERER=ansi`.

## Agent Loop

`agent_loop` is goldfish's first plan/execute framework. It turns a natural-language goal into a short plan, executes one allow-listed `ToolRegistry` tool at a time, records each observation, revises the plan when a fallback is useful, and then writes a final answer.

The loop shape is:

```text
parse_goal -> make_plan -> execute_step -> observe -> revise_plan -> final_answer
```

Allowed tools:

- `skills`
- `web_search`
- `search`
- `rag_query`
- `rag_search`
- `rag_status`
- `memory_show`
- `tools`
- `doctor`
- `dry_run`
- `run_daily`
- `external_cli`

Run from the CLI:

```powershell
goldfish agent "research MCP server commercial opportunities"
goldfish agent "study AI coding agent market trends" --no-llm
goldfish agent "search previous RAG notes" --max-steps 3
goldfish agent "research latest AI coding agent market" --step-timeout 30 --task-timeout 180 --max-failures 3
```

Run inside chat:

```text
/agent research MCP server commercial opportunities and draft 3 business ideas
```

Natural-language research-like requests in chat can also route to the agent loop, for example:

```text
research MCP business opportunities
study RAG evaluation trends
help me research AI coding agent business opportunities
帮我从 MCP 新闻里提炼 3 个商业想法和 MVP
把这条新闻沉淀成永久笔记和 Prompt 草稿
```

Before planning, goldfish now runs a lightweight skill router over the goal. It can select relevant `scripts/goldfish/skills/*/SKILL.md` guidance for retrieval planning, internet search, web research, business ideas, draft writing, knowledge routing, trend analysis, fact checking, source evaluation, external CLI tools, and weekly review. Tool selection still has rule-based fallback, so it works without an LLM API key.

Natural-language chat routing has three layers:

1. Slash commands such as `/web`, `/research`, and `/agent` remain explicit and stable.
2. If an LLM API key is configured, `scripts/goldfish/modules/tool_planner.py` asks the model to choose one allow-listed `ToolRegistry` tool from the current tool descriptions and return strict JSON.
3. If the model is unavailable, low-confidence, or returns an unsafe/unknown tool, goldfish falls back to `scripts/goldfish/config/tool_intents.json`.

This means new ordinary phrasing usually does not require a new intent rule. Use `tool_intents.json` only for deterministic fallback behavior or high-priority local conventions.

Task workspaces are saved under:

```text
scripts/goldfish/output_cache/tasks/task-YYYYMMDD-HHMMSS-xxxx-*/
```

Each workspace contains:

```text
goal.md
failure_policy.json
plan.md
plan_revisions.jsonl
execution_state.json
selected_skills.json
skills.md
observations.json
tool_calls.jsonl
final.md
```

Failure and timeout policy:

- `agent_step_timeout_seconds`: default maximum wait for one tool step.
- `agent_task_timeout_seconds`: default maximum wait for the whole agent loop.
- `agent_max_total_failures`: stop after this many failed observations.
- `agent_max_consecutive_failures`: stop after this many failed observations in a row.

You can override the defaults with:

```powershell
goldfish agent "research MCP opportunities" --step-timeout 20 --task-timeout 120 --max-failures 3 --max-consecutive-failures 2
```

Every observation records `started_at`, `finished_at`, `duration_ms`, `timeout_seconds`, `failure_type`, and `timed_out`. The final `execution_state.json` also includes `failure_policy` and `failure_summary`, so a stopped task can explain whether it ended because the plan completed, max steps were reached, a timeout happened, or the failure budget was exhausted.

Plan/execute behavior:

- If public web research fails, goldfish can revise the plan and fall back to local search.
- If a daily run fails, goldfish can revise the plan and run `doctor`.
- If a goal asks for project/code search after listing external tools, goldfish can use the allow-listed `rg_search` wrapper through `external_cli`.
- `run_daily` defaults to dry-run behavior unless the goal clearly asks to write/save/run for real.
- If a tool times out, goldfish records a timeout observation instead of waiting forever.
- If repeated fallbacks keep failing, goldfish stops with `max_total_failures_reached` or `max_consecutive_failures_reached`.

Safety boundaries:

- All tool execution goes through `ToolRegistry`.
- No arbitrary shell execution from `agent_loop`.
- `external_cli` can only call allow-listed tools from `config/external_tools.json`.
- No API keys are written to task files.
- Tool results are truncated before saving when too long.
- Public web research follows the existing no-login, no-cookie, no-anti-scraping-bypass boundary.

Current first-version limitations:

- Planning is mostly rule-based, with optional LLM final summary only when a configured API key exists.
- It can do short 3-8 step workflows, not long autonomous projects yet.
- It records observations, but does not yet dynamically redraw the startup UI state.
- It can choose existing tools only; it cannot invent new tools.
- Python thread-based step timeouts cannot forcibly kill a handler that is already running; network and external CLI tools still use their own internal timeouts, and the agent loop records the timeout boundary at the orchestration layer.
