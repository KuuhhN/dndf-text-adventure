import { Component, useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

// 世界观词条分类中文名（世界书弹窗）
const LORE_CAT_ZH = {
  geography: "地理",
  faction: "势力",
  history: "历史",
  magic: "魔法",
  religion: "宗教",
};

// 装备槽位（与后端 tools.EQUIP_SLOTS 一致）
const EQUIP_SLOTS = ["weapon", "armor", "trinket"];
const EQUIP_SLOT_ZH = { weapon: "武器", armor: "护甲", trinket: "饰品" };
const EQUIP_ICONS = { weapon: "⚔️", armor: "🛡️", trinket: "✨" };

// ---- 中文化映射（展示层；value/key 保持英文供 SRD 数据与工具调用使用）----
const ZH = {
  // 种族
  Dwarf: "矮人", Elf: "精灵", Human: "人类", Halfling: "半身人",
  Dragonborn: "龙裔", Gnome: "侏儒", "Half-Elf": "半精灵", "Half-Orc": "半兽人", Tiefling: "提夫林",
  // 职业
  Barbarian: "野蛮人", Bard: "诗人", Cleric: "牧师", Druid: "德鲁伊",
  Fighter: "战士", Monk: "武僧", Paladin: "圣武士", Ranger: "游侠",
  Rogue: "游荡者", Sorcerer: "术士", Warlock: "邪术师", Wizard: "法师",
  // 属性
  STR: "力量", DEX: "敏捷", CON: "体质", INT: "智力", WIS: "感知", CHA: "魅力",
  // 技能
  Acrobatics: "特技", "Animal Handling": "驯兽", Arcana: "奥术", Athletics: "运动",
  Deception: "欺瞒", History: "历史", Insight: "洞察", Intimidation: "威吓",
  Investigation: "调查", Medicine: "医疗", Nature: "自然", Perception: "察觉",
  Performance: "表演", Persuasion: "说服", Religion: "宗教", "Sleight of Hand": "巧手",
  "Sleight Of Hand": "巧手", // 部分职业数据用大写 Of
  Stealth: "潜行", Survival: "生存",
  // 常用怪物
  Goblin: "哥布林", Orc: "兽人", Wolf: "狼", "Giant Rat": "巨鼠", "Giant Spider": "巨型蜘蛛",
  Zombie: "僵尸", Skeleton: "骷髅", Kobold: "狗头人", Bandit: "强盗", Bear: "熊",
  "Dire Wolf": "恐狼", Hobgoblin: "霍布哥布林", Bugbear: "熊地精", "Giant Boar": "巨野猪",
  // 专长（2024 SRD 通译）
  Alert: "警觉", "Magic Initiate": "魔法入门", "Savage Attacker": "野蛮攻击者",
  Skilled: "技能熟练", Grappler: "擒抱者", Archery: "箭术", Defense: "防御",
  "Great Weapon Fighting": "巨武器战斗", "Two Weapon Fighting": "双武器战斗",
  "Ability Score Improvement": "属性值提升", "Boon of Combat Prowess": "战斗技巧之赐福",
  "Boon of Dimensional Travel": "位面旅行之赐福", "Boon of Fate": "命运之赐福",
  "Boon of Irresistible Offense": "不可阻挡攻势之赐福", "Boon of Spell Recall": "法术回想之赐福",
  "Boon of Truesight": "真视之赐福", "Boon of the Night Spirit": "夜灵之赐福",
  // 背景
  Acolyte: "侍僧", Criminal: "罪犯", Sage: "贤者", Soldier: "士兵",
  // 常见特性
  Darkvision: "黑暗视觉", "Dwarven Resilience": "矮人韧性", Stonecunning: "岩石智慧",
  "Dwarven Combat Training": "矮人战斗训练", "Tool Proficiency": "工具熟练",
  "Fighting Style": "战斗风格", "Second Wind": "二次呼吸", Rage: "狂暴",
  "Unarmored Defense": "无甲防御", "Sneak Attack": "偷袭", "Spellcasting": "施法能力",
  "Cunning Action": "狡诈行动", "Action Surge": "动作如潮", "Keen Senses": "敏锐感官",
  "Fey Ancestry": "妖精血统", "Trance": "出神", Lucky: "幸运", "Brave": "无畏",
  "Halfling Nimbleness": "半身人灵巧", "Naturally Stealthy": "天生潜行",
  "Hellish Resistance": "地狱抗性", "Infernal Legacy": "地狱遗产", "Savage Attacks": "野蛮攻击",
  "Draconic Ancestry": "龙族血统", "Breath Weapon": "吐息武器", "Damage Resistance": "伤害抗性",
  "Extra Language": "额外语言", "Skill Versatility": "技能多面手",
  "Dwarven Toughness": "矮人坚韧", "Gnome Cunning": "侏儒狡黠",
  "Artificer's Lore": "工匠学识", Tinker: "工匠", "High Elf Cantrip": "高等精灵戏法",
  "Relentless Endurance": "不屈坚韧", "Menacing": "威吓气质",
  // 职业 1-2 级特性（向导展示）
  "Action Surge (1 use)": "动作如潮（1次/短休）", "Arcane Recovery": "奥术恢复",
  "Arcane Tradition": "奥术传统", "Bardic Inspiration (d6)": "吟游激励（d6）",
  "Bonus Cantrip": "额外戏法", "Bonus Proficiency": "额外熟练",
  "Channel Divinity (1/rest)": "引导神力（1次/短休）",
  "Channel Divinity: Preserve Life": "引导神力：维系生命",
  "Channel Divinity: Turn Undead": "引导神力：驱散不死",
  "Danger Sense": "危险感知", "Dark One's Blessing": "黑暗恩赐",
  "Disciple of Life": "生命门徒", "Divine Domain": "神圣领域",
  "Divine Domain feature": "神圣领域特性", "Divine Sense": "神圣感知",
  "Divine Smite": "神圣打击", "Domain Spells": "领域法术",
  "Draconic Resilience": "龙族韧性", "Dragon Ancestor": "龙族先祖",
  "Druid Circle": "德鲁伊结社", Druidic: "德鲁伊密语",
  "Eldritch Invocations": "邪术祈唤", "Evocation Savant": "塑能专精",
  Expertise: "专精", "Favored Enemy (1 type)": "宿敌（1类）",
  "Flexible Casting: Converting Spell Slot": "灵活施法：转化法术位",
  "Flexible Casting: Creating Spell Slots": "灵活施法：创造法术位",
  "Flurry of Blows": "疾风连击", "Font of Magic": "魔力泉源",
  "Jack of All Trades": "万事通", Ki: "气", "Lay on Hands": "圣疗",
  "Martial Arts": "武艺", "Natural Explorer (1 terrain type)": "自然探索者（1类地形）",
  "Natural Recovery": "自然恢复", "Otherworldly Patron": "异界宗主",
  "Pact Magic": "契术魔法", "Patient Defense": "凝神防御",
  "Reckless Attack": "鲁莽攻击", "Sculpt Spells": "法术塑形",
  "Song of Rest (d6)": "休憩之歌（d6）", "Sorcerous Origin": "术法起源",
  "Spellcasting: Bard": "施法能力：吟游诗人", "Spellcasting: Cleric": "施法能力：牧师",
  "Spellcasting: Druid": "施法能力：德鲁伊", "Spellcasting: Paladin": "施法能力：圣武士",
  "Spellcasting: Ranger": "施法能力：游侠", "Spellcasting: Sorcerer": "施法能力：术士",
  "Spellcasting: Wizard": "施法能力：法师",
  "Step of the Wind": "御风步", "Thieves' Cant": "盗贼黑话",
  "Unarmored Movement": "无甲移动",
  "Wild Shape (CR 1/4 or below, no flying or swim speed)": "荒野变形（CR 1/4以下）",
  // 职业熟练项（护甲/武器/工具）
  "All armor": "全部护甲", "Light Armor": "轻甲", "Medium Armor": "中甲",
  "Shields": "盾牌", "Simple Weapons": "简易武器", "Martial Weapons": "军用武器",
  "Clubs": "木棒", "Daggers": "匕首", "Darts": "飞镖", "Javelins": "标枪",
  "Maces": "钉头锤", "Quarterstaffs": "长棍", "Rapiers": "细剑",
  "Shortswords": "短剑", "Sickles": "镰刀", "Slings": "投石索", "Spears": "长矛",
  "Longswords": "长剑", "Hand crossbows": "手弩", "Crossbows, light": "轻弩",
  "Thieves' Tools": "盗贼工具", "Calligrapher's Supplies": "书法工具", "Saving Throw: STR": "豁免：力量",
  "Saving Throw: DEX": "豁免：敏捷", "Saving Throw: CON": "豁免：体质",
  "Saving Throw: INT": "豁免：智力", "Saving Throw: WIS": "豁免：感知",
  "Saving Throw: CHA": "豁免：魅力",
};
const t = (k) => ZH[k] || k; // 未知名称回退英文
// 熟练项显示：Skill:/Tool: 前缀转中文（工具名有 ZH 映射则翻译）
const zhProf = (p) => (p.startsWith("Tool: ") ? `工具：${t(p.replace("Tool: ", ""))}` : t(p.replace("Skill: ", "")));

// 错误边界：任何渲染/事件错误显示在页面而非白屏，便于定位与反馈
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("RenderError:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="crash-box">
          <h3>⚠️ 页面出错了</h3>
          <pre>{String(this.state.error && (this.state.error.stack || this.state.error.message || this.state.error))}</pre>
          <button className="primary" onClick={() => window.location.reload()}>重新加载</button>
        </div>
      );
    }
    return this.props.children;
  }
}

// 全局事件错误（onChange/onClick 内抛错不会被 ErrorBoundary 捕获）——显示在页面底部
window.addEventListener("error", (e) => {
  const box = document.getElementById("runtime-error");
  if (box) box.textContent = `运行时错误：${e.message}`;
});

// 主动能力展示（与后端 tools.FEATURE_ACTIONS 白名单对应）
const FEATURES_UI = {
  "second-wind": { zh: "二次呼吸", action: "附赠动作", rest: "短休" },
  rage: { zh: "狂暴", action: "附赠动作", rest: "长休" },
  "bardic-inspiration-d6": { zh: "吟游激励", action: "附赠动作", rest: "长休" },
  "lay-on-hands": { zh: "圣疗", action: "动作", rest: "长休" },
  "breath-weapon": { zh: "吐息武器", action: "动作", rest: "短休", hint: "（目标最近的敌人）" },
  "cunning-action": { zh: "狡诈行动", action: "附赠动作", rest: "每回合", hint: "（疾走/脱离/巧手）" },
};

// 被动能力展示（与后端 tools.PASSIVES 对应——展示的能力全部引擎生效）
const PASSIVES_UI = {
  "savage-attacker": { zh: "野蛮攻击者", desc: "武器伤害骰掷两次取高（自动）", src: "专长" },
  alert: { zh: "警觉", desc: "先攻 +5，战斗开局更快（自动）", src: "专长" },
  skilled: { zh: "技能熟练", desc: "额外 3 个技能熟练（已生效）", src: "专长" },
  darkvision: { zh: "黑暗视觉", desc: "黑暗中视物如常（自动）", src: "种族" },
  lucky: { zh: "幸运", desc: "检定大失败自动重掷（1次/长休）", src: "种族" },
  "relentless-endurance": { zh: "不屈坚韧", desc: "濒死时回到 1 点生命（1次/长休）", src: "种族" },
  "dwarven-resilience": { zh: "矮人韧性", desc: "中毒伤害减半（自动）", src: "种族" },
  "damage-resistance": { zh: "伤害抗性", desc: "对应元素伤害减半（自动）", src: "种族" },
  "hellish-resistance": { zh: "地狱抗性", desc: "火焰伤害减半（自动）", src: "种族" },
  "draconic-ancestry": { zh: "龙族血统", desc: "对应龙类元素伤害减半（自动）", src: "种族" },
};

// 技能一句话用途（游戏内技能面板）
const SKILL_HINTS = {
  Acrobatics: "翻越障碍、保持平衡、挣脱束缚",
  "Animal Handling": "安抚或骑乘动物",
  Arcana: "识别法术与魔法造物",
  Athletics: "攀爬、游泳、角力",
  Deception: "说谎骗过对方",
  History: "回忆历史与传说",
  Insight: "识破谎言、读懂意图",
  Intimidation: "用威胁让对方屈服",
  Investigation: "搜索房间、拼凑线索",
  Medicine: "稳定濒死同伴、诊断伤病",
  Nature: "辨认植物、动物与地形",
  Perception: "发现隐藏的敌人、陷阱、线索",
  Performance: "演奏表演、取悦观众",
  Persuasion: "说服 NPC 答应你",
  Religion: "辨认宗教符号与仪式",
  "Sleight of Hand": "开锁、扒窃、藏匿小物",
  Stealth: "不被发现地潜行移动",
  Survival: "追踪猎物、野外求生",
};

// 错误消息里的英文名替换成中文（后端错误用英文 key 报专长/背景名）
const zhError = (msg) => {
  let m = msg;
  for (const en of Object.keys(ZH)) m = m.split(en).join(ZH[en]);
  return m;
};

function App() {
  const [races, setRaces] = useState([]);
  const [classes, setClasses] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState(null); // {id, character, history}
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [inCombat, setInCombat] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/api/races`).then((r) => r.json()).then((d) => setRaces(d.races));
    fetch(`${API}/api/classes`).then((r) => r.json()).then((d) => setClasses(d.classes));
    refreshSessions();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function refreshSessions() {
    const d = await (await fetch(`${API}/api/sessions`)).json();
    setSessions(d.sessions);
  }

  async function loadSession(id) {
    const d = await (await fetch(`${API}/api/session/${id}`)).json();
    setSession({ id: d.id, character: d.character });
    setInCombat(Boolean(d.in_combat));
    setMessages(d.history.filter((h) => h.role !== "tool"));
  }

  async function createCharacter(form) {
    const resp = await fetch(`${API}/api/character`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const d = await resp.json();
    if (!resp.ok) {
      alert(zhError(d.error) || "创建失败");
      return;
    }
    setSession({ id: d.session_id, character: d.character });
    setMessages([]);
    refreshSessions();
    // 自动触发 DM 开场（显式传 sessionId，避免 setState 异步导致闭包拿不到）
    setTimeout(() => sendText("冒险开始！请描绘酒馆场景，介绍我面前的机会。", d.session_id), 100);
  }

  async function sendText(text, sessionId = session?.id) {
    if (!text.trim() || busy || !sessionId) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const resp = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") continue;
          let evt;
          try {
            evt = JSON.parse(payload);
          } catch {
            continue; // 容错：坏行跳过，不中断流解析
          }
          if (evt.type === "delta") {
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                ...next[next.length - 1],
                content: next[next.length - 1].content + evt.text,
              };
              return next;
            });
          } else if (evt.type === "tool") {
            setMessages((prev) => [...prev, { role: "tool", content: formatTool(evt) }]);
            // 工具副作用（HP/敌人/经验）后刷新角色卡
            const d = await (await fetch(`${API}/api/session/${sessionId}`)).json();
            setSession((prev) => ({ ...prev, character: d.character }));
          } else if (evt.type === "state") {
            setInCombat(Boolean(evt.in_combat));
          } else if (evt.type === "error") {
            setMessages((prev) => [...prev, { role: "error", content: evt.text }]);
          }
        }
      }
    } finally {
      setBusy(false); // 网络中断/异常也复位按钮，不卡死
    }
  }

  function send() {
    sendText(input);
  }

  return (
    <ErrorBoundary>
      <div className="app">
      {!session ? (
        <div className="home">
          <CreateWizard races={races} classes={classes} onSubmit={createCharacter} />
          {sessions.length > 0 && (
            <div className="continue">
              <h3>📜 继续冒险</h3>
              {sessions.slice(0, 6).map((s) => (
                <button key={s.id} className="save-item" onClick={() => loadSession(s.id)}>
                  {s.name} · {s.updated_at?.slice(0, 16)}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <GameView
          character={session.character}
          messages={messages}
          input={input}
          busy={busy}
          inCombat={inCombat}
          setInput={setInput}
          send={send}
          sendText={sendText}
          bottomRef={bottomRef}
          onNewGame={() => { setSession(null); setInCombat(false); }}
          sessionId={session.id}
          onCharacterUpdate={(ch) => setSession((prev) => ({ ...prev, character: ch }))}
        />
      )}
      <div id="runtime-error" className="runtime-error" />
    </div>
    </ErrorBoundary>
  );
}

const PB_COST = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
const PB_BUDGET = 27;
const AB_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];

function CreateWizard({ races, classes, onSubmit }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: "", race: "", class_name: "", method: "point-buy",
    abilities: { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 },
    chosen_skills: [], skilled_skills: [], expertise_skills: [], background: "", feat: "",
  });
  const [raceDetail, setRaceDetail] = useState(null);
  const [classDetail, setClassDetail] = useState(null);
  const [feats, setFeats] = useState([]);
  const [backgrounds, setBackgrounds] = useState([]);
  const [rolled, setRolled] = useState(null);
  const set = (k, v) => setForm((prev) => ({ ...prev, [k]: v }));

  async function pickRace(name) {
    set("race", name);
    const d = await (await fetch(`${API}/api/races/${name}`)).json();
    setRaceDetail(d);
  }
  async function pickClass(name) {
    set("class_name", name);
    set("chosen_skills", []);
    set("skilled_skills", []);  // 换职业后原自选技能可能已熟练/不可用，清空重选
    set("expertise_skills", []);  // 换职业后专精选择失效，清空重选
    const d = await (await fetch(`${API}/api/classes/${name}`)).json();
    setClassDetail(d);
    if (name && !feats.length) {
      const f = await (await fetch(`${API}/api/feats`)).json();
      setFeats(f.feats.filter((x) => ["origin", "general"].includes(x.type)));
      const b = await (await fetch(`${API}/api/backgrounds`)).json();
      setBackgrounds(b.backgrounds);
    }
  }
  async function rollPreview() {
    const d = await (await fetch(`${API}/api/roll-abilities`)).json();
    setRolled(d.abilities);
  }

  // 延迟求值（箭头函数）：hasSkilled/hasExpertise 在其后定义，立即求值会触发 TDZ 崩溃（选满技能后白屏）
  const canNext = () =>
    (step === 1 && form.race) || (step === 2 && form.class_name) ||
    (step === 3 && (form.method === "rolled" ? rolled : spent() <= PB_BUDGET)) ||
    (step === 4 && form.background) ||
    (step === 5 && form.chosen_skills.length === (classDetail?.skill_choices?.choose ?? 0) &&
      (form.feat !== "Skilled" || form.skilled_skills.length === 3) &&
      (!hasExpertise || form.expertise_skills.length === 2)) ||
    (step === 6 && form.name.trim());

  function spent() {
    return Object.values(form.abilities).reduce((s, v) => s + (PB_COST[v] ?? 0), 0);
  }
  function bump(ab, delta) {
    const cur = form.abilities[ab];
    const next = cur + delta;
    if (next < 8 || next > 15) return;
    if (delta > 0 && spent() + PB_COST[next] - PB_COST[cur] > PB_BUDGET) return;
    set("abilities", { ...form.abilities, [ab]: next });
  }

  const totalMod = {};
  AB_ORDER.forEach((ab) => {
    const base = form.method === "rolled" && rolled ? rolled[ab] : form.abilities[ab];
    const bonus = raceDetail?.ability_bonuses?.find((b) => b.ability === ab)?.bonus || 0;
    totalMod[ab] = base + bonus;
  });

  const next = () => setStep(step + 1);
  const prev = () => setStep(Math.max(1, step - 1));
  const steps = ["种族", "职业", "属性", "专长·背景", "技能", "名字"];
  // 背景已提供的技能（技能页只读展示）
  const bgSkills = (backgrounds.find((b) => b.name === form.background)?.proficiencies || [])
    .map((p) => p.replace("Skill: ", ""))
    .filter((s) => SKILL_HINTS[s]);
  const bgFeat = backgrounds.find((b) => b.name === form.background)?.feat;
  const hasSkilled = form.feat === "Skilled";
  // 专精（游荡者 1 级）：1 级特性含 Expertise
  const hasExpertise = (classDetail?.level_features?.["1"] || []).some((f) => f.name === "Expertise");
  // 职业固定熟练技能（技能页置灰用，提前计算避免每次渲染重建）
  const classFixedSkills = (classDetail?.proficiencies || [])
    .filter((p) => String(p).startsWith("Skill: "))
    .map((p) => String(p).replace("Skill: ", ""));

  return (
    <div className="wizard multi">
      <h1>🗡️ DNDF 文字冒险</h1>
      <p className="sub">创建你的冒险者，AI 地下城主将为你编织传奇</p>
      <div className="steps">
        {steps.map((s, i) => (
          <div key={s} className={`step-dot ${i + 1 === step ? "on" : ""} ${i + 1 < step ? "done" : ""}`}>
            {i + 1 < step ? "✓" : i + 1}
            <span>{s}</span>
          </div>
        ))}
      </div>

      <div className="step-body">
        {step === 1 && (
          <div className="pick-grid">
            <div className="pick-list">
              {races.map((r) => (
                <button key={r} className={`pick-card ${form.race === r ? "on" : ""}`} onClick={() => pickRace(r)}>
                  <b>{t(r)}</b>
                </button>
              ))}
            </div>
            <div className="pick-detail">
              {raceDetail ? (
                <>
                  <h3>{t(raceDetail.name)}</h3>
                  <div className="detail-meta">
                    {raceDetail.ability_bonuses.length > 0 && (
                      <>加成 {raceDetail.ability_bonuses.map((b) => `${t(b.ability)}+${b.bonus}`).join(" ")}</>
                    )}
                  </div>
                  <ul className="detail-traits">
                    {raceDetail.traits.map((tr) => (
                      <FeatureItem key={tr.index} f={tr} />
                    ))}
                  </ul>
                </>
              ) : (
                <div className="detail-empty">选择种族查看特性</div>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="pick-grid">
            <div className="pick-list">
              {classes.map((c) => (
                <button key={c} className={`pick-card ${form.class_name === c ? "on" : ""}`} onClick={() => pickClass(c)}>
                  <b>{t(c)}</b>
                </button>
              ))}
            </div>
            <div className="pick-detail">
              {classDetail ? (
                <>
                  <h3>{t(classDetail.name)}</h3>
                  <div className="detail-meta">
                    生命骰 d{classDetail.hit_die} · 豁免 {classDetail.saving_throws.map(t).join("/")}
                    {classDetail.skill_choices?.choose ? ` · 可选技能 ${classDetail.skill_choices.choose} 个` : ""}
                  </div>
                  {classDetail.proficiencies?.length > 0 && (
                    <div className="detail-meta">
                      熟练：{classDetail.proficiencies.map(t).join("、")}
                    </div>
                  )}
                  <ul className="detail-traits">
                    {Object.entries(classDetail.level_features).flatMap(([lv, feats]) =>
                      feats.map((f) => (
                        <FeatureItem key={`${lv}-${f.index}`} f={f} />
                      ))
                    )}
                  </ul>
                </>
              ) : (
                <div className="detail-empty">选择职业查看技能与特性</div>
              )}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="pb-panel">
            <div className="pb-mode">
              <label><input type="radio" checked={form.method === "point-buy"} onChange={() => set("method", "point-buy")} /> 标准购点（27 点）</label>
              <label><input type="radio" checked={form.method === "rolled"} onChange={() => { set("method", "rolled"); if (!rolled) rollPreview(); }} /> 骰点（4d6 取 3 高）</label>
              {form.method === "rolled" && <button className="pb-reroll" onClick={rollPreview}>🎲 重掷</button>}
            </div>
            <div className="pb-grid">
              {AB_ORDER.map((ab) => {
                const base = form.method === "rolled" && rolled ? rolled[ab] : form.abilities[ab];
                return (
                  <div key={ab} className="pb-ability">
                    <div className="pb-name">{t(ab)}</div>
                    {form.method === "point-buy" ? (
                      <>
                        <div className="pb-score">{base}</div>
                        <div className="pb-btns">
                          <button onClick={() => bump(ab, -1)} disabled={base <= 8}>−</button>
                          <button onClick={() => bump(ab, 1)} disabled={base >= 15 || spent() + PB_COST[base + 1] - PB_COST[base] > PB_BUDGET}>＋</button>
                        </div>
                        <div className="pb-cost">{PB_COST[base]} 点</div>
                      </>
                    ) : (
                      <div className="pb-score">{base}</div>
                    )}
                    <div className="pb-total">
                      修正 {mod(Math.floor((totalMod[ab] - 10) / 2))} <small>（含种族 {mod(totalMod[ab] - base)}）</small>
                    </div>
                  </div>
                );
              })}
            </div>
            {form.method === "point-buy" && (
              <div className={`pb-budget ${spent() > PB_BUDGET ? "over" : ""}`}>
                已用 {spent()}/{PB_BUDGET} 点
              </div>
            )}
            <p className="pb-note">购点范围 8-15，按 5e 规则书花费表严格计算；种族加成自动应用。</p>
          </div>
        )}

        {step === 4 && (
          <div className="feat-panel">
            <h3>背景（提供技能熟练 + 专长）</h3>
            <div className="bg-list">
              {backgrounds.map((b) => (
                <button key={b.index} className={`bg-card ${form.background === b.name ? "on" : ""}`} onClick={() => {
                  // 重选当前已选背景不重置（防误触丢失已选技能）
                  if (form.background === b.name) return;
                  set("background", b.name);
                  // 背景赠送专长与已选专长重复时自动取消选择
                  if (form.feat === b.feat) set("feat", "");
                  // 换背景后原自选技能可能已被背景覆盖为熟练，清空重选
                  set("chosen_skills", []);
                  set("skilled_skills", []);
                  set("expertise_skills", []);
                }}>
                  <b>{t(b.name)}</b>
                  <span>赠送专长：{t(b.feat)}</span>
                  <span>技能：{b.proficiencies.map(zhProf).join("、")}</span>
                </button>
              ))}
            </div>
            <h3>1 级专长（可选）</h3>
            <div className="bg-list">
              {feats.filter((f) => f.name !== bgFeat).map((f) => (
                <button key={f.index} className={`bg-card ${form.feat === f.name ? "on" : ""}`} onClick={() => set("feat", form.feat === f.name ? "" : f.name)}>
                  <b>{t(f.name)}</b>
                  <span className="feat-sum">{f.summary || (f.desc ? f.desc.slice(0, 60) + "…" : "")}</span>
                </button>
              ))}
            </div>
            <p className="pb-note">技能熟练专长会在下一步让你额外自选 3 个技能。</p>
          </div>
        )}

        {step === 5 && (
          <div className="skill-pick big">
            <div className="skill-pick-title">
              选择熟练技能（选 {classDetail?.skill_choices?.choose ?? 0} 个）
            </div>
            <div className="skill-pick-opts">
              {(classDetail?.skill_choices?.options ?? []).map((s) => (
                <label key={s} className={`chip ${form.chosen_skills.includes(s) ? "on" : ""} ${form.skilled_skills.includes(s) || bgSkills.includes(s) ? "taken" : ""}`}>
                  <input
                    type="checkbox"
                    disabled={form.skilled_skills.includes(s) || bgSkills.includes(s)}
                    checked={form.chosen_skills.includes(s)}
                    onChange={() => {
                      const picked = form.chosen_skills.includes(s)
                        ? form.chosen_skills.filter((x) => x !== s)
                        : [...form.chosen_skills, s].slice(0, classDetail.skill_choices.choose);
                      set("chosen_skills", picked);
                    }}
                  />
                  {t(s)}
                </label>
              ))}
            </div>
            {bgSkills.length > 0 && (
              <div className="bg-skills-note">
                🏷️ 背景「{t(form.background)}」已提供：{bgSkills.map(t).join("、")}（自动熟练，无需选择）
              </div>
            )}
            {hasSkilled && (
              <>
                <div className="skill-pick-title">
                  🎓 技能熟练专长：再选 3 个技能（从所有技能中选）
                </div>
                <div className="skill-pick-opts">
                  {Object.keys(SKILL_HINTS).map((s) => {
                    const taken = form.chosen_skills.includes(s) || bgSkills.includes(s) || classFixedSkills.includes(s);
                    const picked = form.skilled_skills.includes(s);
                    return (
                      <label key={s} className={`chip ${picked ? "on" : ""} ${taken ? "taken" : ""}`}>
                        <input
                          type="checkbox"
                          disabled={taken}
                          checked={picked}
                          onChange={() => {
                            const next = picked
                              ? form.skilled_skills.filter((x) => x !== s)
                              : [...form.skilled_skills, s].slice(0, 3);
                            set("skilled_skills", next);
                          }}
                        />
                        {t(s)}
                      </label>
                    );
                  })}
                </div>
                <p className="pb-note">已选 {form.skilled_skills.length}/3（灰色为已熟练技能，不可重复选）</p>
              </>
            )}
            {hasExpertise && (
              <>
                <div className="skill-pick-title">
                  🎯 专精（{t(form.class_name)}）：选 2 个已熟练技能，检定熟练加值翻倍
                </div>
                <div className="skill-pick-opts">
                  {Object.keys(SKILL_HINTS).map((s) => {
                    const prof = form.chosen_skills.includes(s) || bgSkills.includes(s) ||
                      classFixedSkills.includes(s) || form.skilled_skills.includes(s);
                    const picked = form.expertise_skills.includes(s);
                    return (
                      <label key={s} className={`chip ${picked ? "on" : ""} ${!prof ? "taken" : ""}`}>
                        <input
                          type="checkbox"
                          disabled={!prof}
                          checked={picked}
                          onChange={() => {
                            const next = picked
                              ? form.expertise_skills.filter((x) => x !== s)
                              : [...form.expertise_skills, s].slice(0, 2);
                            set("expertise_skills", next);
                          }}
                        />
                        {t(s)}
                      </label>
                    );
                  })}
                </div>
                <p className="pb-note">已选 {form.expertise_skills.length}/2（灰色为未熟练技能，专精只能选已熟练）</p>
              </>
            )}
          </div>
        )}

        {step === 6 && (
          <div className="final-step">
            <label>冒险者之名
              <input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="例如：铁锤·铜须" />
            </label>
            <div className="final-summary">
              <div><b>{t(form.race)}</b> {t(form.class_name)} · Lv.1</div>
              <div>背景：{form.background ? t(form.background) : "—"} · 专长：{form.feat ? t(form.feat) : "—"}</div>
              <div>属性：{AB_ORDER.map((ab) => `${t(ab)} ${totalMod[ab]}`).join(" · ")}</div>
            </div>
          </div>
        )}
      </div>

      <div className="step-nav">
        {step > 1 && <button className="ghost-btn" onClick={prev}>← 上一步</button>}
        {step < 6 ? (
          <button className="primary" disabled={!canNext()} onClick={next}>下一步 →</button>
        ) : (
          <button className="primary" disabled={!canNext()} onClick={() => onSubmit(form)}>开始冒险</button>
        )}
        {!canNext() && step === 5 && (
          <p className="step-hint">
            {(() => {
              const choose = classDetail?.skill_choices?.choose ?? 0;
              if (form.chosen_skills.length !== choose) return `还需选 ${choose - form.chosen_skills.length} 个职业技能`;
              if (hasSkilled && form.skilled_skills.length !== 3) return `技能熟练专长还需选 ${3 - form.skilled_skills.length} 个技能`;
              if (hasExpertise && form.expertise_skills.length !== 2) return `专精还需选 ${2 - form.expertise_skills.length} 个技能`;
              return "";
            })()}
          </p>
        )}
        {!canNext() && step === 4 && <p className="step-hint">请先选择一个背景</p>}
      </div>
    </div>
  );
}

function mod(v) {
  return v >= 0 ? `+${v}` : `${v}`;
}

// 特性条目：一句话用途（大字）+ 完整规则折叠。用户要求"一眼看懂能干什么"。
function FeatureItem({ f }) {
  const show = f.summary || "";
  const hasMore = show && f.desc && f.desc !== show;
  return (
    <li>
      <b>{t(f.name)}</b>
      {show ? (
        <>
          <p className="feat-sum">{show}</p>
          {hasMore && (
            <details><summary>📖 完整规则</summary><p className="feat-full">{f.desc}</p></details>
          )}
        </>
      ) : (
        f.desc && <p>{f.desc.slice(0, 70)}{f.desc.length > 70 ? "…" : ""}</p>
      )}
    </li>
  );
}

function formatTool(evt) {
  const r = evt.result;
  if (r.error) return `⚠️ ${r.error}`;
  switch (evt.call.name) {
    case "roll_dice":
      return `🎲 掷 ${r.expression}：${r.rolls.join(" + ")}${r.total !== r.rolls[0] ? ` = ${r.total}` : ""}${r.crit ? "  💥重击！" : ""}${r.fumble ? "  💀失手！" : ""}`;
    case "ability_check":
      return `🎯 ${r.label}：D20 ${r.d20} + ${r.modifier} = ${r.total}${r.dc != null ? `（DC ${r.dc}）${r.success ? " ✅成功" : " ❌失败"}` : ""}${r.lucky_reroll ? " 🍀幸运重掷" : ""}${r.crit ? "  💥大成功！" : ""}${r.fumble ? "  💀大失败！" : ""}`;
    case "attack":
      return `⚔️ 攻击 ${r.target}（AC ${r.target_ac}）：攻击掷 ${r.attack_roll} + ${r.to_hit_bonus} = ${r.attack_total} → ${r.hit ? "命中！" : "未命中"}${r.damage ? `，伤害 ${r.damage}${r.crit ? "（重击！）" : ""}` : ""}`;
    case "lookup":
      return `📖 ${r.name}: ${r.hp !== undefined ? `HP ${r.hp} · AC ${r.ac}` : r.level !== undefined ? `Lv.${r.level} ${r.school}` : r.category}`;
    case "post_quest":
      return `📜 ${r.quest.title}${r.quest.reward ? `（${r.quest.reward}）` : ""} → ${r.quest.status === "accepted" ? "已接下" : "已登记到告示栏"}`;
    case "add_item":
      return `🎒 获得 ${r.item.name}${r.item.quantity > 1 ? ` ×${r.item.quantity}` : ""}${r.note === "数量增加" ? "（数量 +1）" : ""}`;
    case "remove_item":
      return `${r.removed ? "🗑️ 已移除" : "🎒 已消耗"} ${r.item.name}${r.item.quantity ? `（剩余 ×${r.item.quantity}）` : ""}`;
    case "use_feature": {
      const d = r.healed ? `恢复 ${r.healed} HP` : r.damage !== undefined ? (r.saved ? "敌人躲过了吐息" : `造成 ${r.damage} 伤害`) : r.rage ? "进入狂暴！" : r.note || "";
      return `⚡ ${r.feature_zh}（${r.action}）：${d}${r.remaining != null ? ` · 剩余 ${r.remaining} 次` : ""}`;
    }
    default:
      return JSON.stringify(r);
  }
}

function GameView({ character, messages, input, busy, inCombat, setInput, send, sendText, bottomRef, onNewGame, sessionId, onCharacterUpdate }) {
  const c = character;
  const [modal, setModal] = useState(null); // null | "quests" | "shop" | "skills" | "map" | "lore"
  const [shopItems, setShopItems] = useState([]);
  const [worldMap, setWorldMap] = useState({});
  const [modalMsg, setModalMsg] = useState("");
  const [buying, setBuying] = useState(false); // 购买请求中（防双击重复扣款）

  // 当前区域（character.location + 世界地图；旧角色无 location 字段时默认酒馆）
  const curLoc = worldMap[c.location || "tavern"] || null;
  const shopLevel = curLoc?.shop_level || 0;
  const hasShop = shopLevel > 0;

  function openModal(name) {
    setModalMsg("");
    if (name === "shop" && shopItems.length === 0) {
      fetch(`${API}/api/shop`).then((r) => r.json()).then((d) => setShopItems(d.items || []))
        .catch(() => setModalMsg("❌ 商店加载失败，请重试"));
    }
    if (name === "map" && Object.keys(worldMap).length === 0) {
      fetch(`${API}/api/world`).then((r) => r.json()).then((d) => setWorldMap(d.map || {}))
        .catch(() => setModalMsg("❌ 地图加载失败，请重试"));
    }
    setModal(name);
  }

  async function acceptQuest(title) {
    setModalMsg("");
    try {
      const r = await fetch(`${API}/api/quests/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, title }),
      });
      const d = await r.json();
      if (!r.ok) return setModalMsg(`❌ ${d.error || "操作失败"}`);
      onCharacterUpdate(d.character);
      setModalMsg(`✅ ${d.result?.note || "已接下"}`);
    } catch (e) {
      setModalMsg("❌ 网络错误，请重试");
    }
  }

  async function buyItem(item) {
    if (buying) return; // 防双击重复扣款
    setBuying(true);
    setModalMsg("");
    try {
      const r = await fetch(`${API}/api/shop/buy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, item, quantity: 1 }),
      });
      const d = await r.json();
      if (!r.ok) return setModalMsg(`❌ ${d.error || "购买失败"}`);
      onCharacterUpdate(d.character);
      setModalMsg(`✅ ${d.result?.note || "购买成功"}`);
    } catch (e) {
      setModalMsg("❌ 网络错误，请重试");
    } finally {
      setBuying(false);
    }
  }

  async function equipItem(item, slot) {
    const r = await fetch(`${API}/api/equipment/equip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, item, slot }),
    });
    const d = await r.json();
    if (!r.ok) return setModalMsg(`❌ ${d.error || "装备失败"}`);
    onCharacterUpdate(d.character);
    setModalMsg(`✅ ${d.result?.note || "已装备"}`);
  }

  async function unequipItem(slot) {
    const r = await fetch(`${API}/api/equipment/unequip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, slot }),
    });
    const d = await r.json();
    if (!r.ok) return setModalMsg(`❌ ${d.error || "卸下失败"}`);
    onCharacterUpdate(d.character);
    setModalMsg(`✅ ${d.result?.note || "已卸下"}`);
  }

  const availableQuests = (c.quests || []).filter((q) => q.status !== "accepted");
  const todoQuests = (c.quests || []).filter((q) => q.status === "accepted");
  const hasQuestNotice = availableQuests.length > 0;
  return (
    <div className="game">
      <aside className="sheet">
        <div className="sheet-head">
          <h2>{c.name}</h2>
          <div className="meta">
            {t(c.race)} {t(c.class)} · Lv.{c.level}
          </div>
          {curLoc && (
            <div className="meta loc">📍 {curLoc.name}{shopLevel > 0 ? ` · 🏪 ${shopLevel} 级商货` : " · 无商店"}</div>
          )}
          <div className="bars">
            <div className="bar">❤️ HP {c.current_hp}/{c.max_hp} · Lv.{c.level} · XP {c.xp}</div>
            <div className="bar">🛡️ AC {c.ac} · 熟练 +{c.proficiency_bonus}</div>
          </div>
          {c.passives?.length > 0 && (
            <div className="passive-bar">
              <h3>🛡️ 被动能力 <small>（自动生效）</small></h3>
              {c.passives.map((p) => {
                const spec = PASSIVES_UI[p];
                if (!spec) return null;
                return (
                  <div key={p} className="passive-item" title={`来源：${spec.src}`}>
                    <b>{spec.zh}</b>
                    <small>{spec.desc}</small>
                  </div>
                );
              })}
              {c.expertise_skills?.length > 0 && (
                <div className="passive-item">
                  <b>专精</b>
                  <small>{c.expertise_skills.map(t).join("、")} 检定熟练加值翻倍（自动）</small>
                </div>
              )}
            </div>
          )}
          {c.combat?.feature_uses && Object.keys(c.combat.feature_uses).length > 0 && (
            <div className="ability-bar">
              <h3>⚡ 可用能力 <small>（用了即消耗）</small></h3>
              {Object.entries(c.combat.feature_uses).map(([key, u]) => {
                const spec = FEATURES_UI[key];
                if (!spec) return null;
                const spent = u.total != null && u.remaining <= 0;
                return (
                  <button
                    key={key}
                    className={`ability-btn ${spent ? "spent" : ""}`}
                    disabled={spent}
                    title={spec.hint || ""}
                    onClick={() => !busy && sendText(`我使用能力【${spec.zh}】${spec.hint || ""}！`)}
                  >
                    <b>{spec.zh}</b>
                    <small>{spec.action}</small>
                    {u.total != null ? <em>{spent ? "已用完" : `×${u.remaining}`}·{spec.rest}</em> : <em>{spec.rest}</em>}
                  </button>
                );
              })}
            </div>
          )}
          {(c.combat?.enemies?.length > 0) && (
            <div className="enemies">
              <h3>⚔️ 敌人</h3>
              {c.combat.enemies.map((e, i) => (
                <div key={i} className="enemy">
                  <span>{t(e.name)}</span>
                  <div className="hp-bar">
                    <div
                      className="hp-fill"
                      style={{ width: `${Math.max(0, (e.hp / e.max_hp) * 100)}%` }}
                    />
                  </div>
                  <span className="hp-num">{e.hp}/{e.max_hp}</span>
                </div>
              ))}
            </div>
          )}
        {c.equipment && (Object.values(c.equipment).some(Boolean) ? (
          <div className="equipment">
            <h3>⚔️ 已装备</h3>
            {Object.entries(c.equipment).map(([slot, item]) => (
              <div key={slot} className="equip-row">
                <span className="equip-slot">{EQUIP_SLOT_ZH[slot]}</span>
                {item ? (
                  <>
                    <span className="equip-item">{item}</span>
                    <button className="equip-btn" onClick={() => unequipItem(slot)} disabled={busy}>卸下</button>
                  </>
                ) : (
                  <span className="equip-empty">空</span>
                )}
              </div>
            ))}
          </div>
        ) : null)}
        {c.inventory?.length > 0 && (
          <div className="inventory">
            <h3>🎒 背包 {c.gold > 0 && <small>· 💰 {c.gold} 金币</small>}</h3>
            {c.inventory.map((it, i) => (
              <div key={i} className="inv-item" title={it.description || ""}>
                <span className="inv-name">{it.name}</span>
                {it.quantity > 1 && <span className="inv-qty">×{it.quantity}</span>}
                {it.description && <span className="inv-desc">{it.description}</span>}
                <div className="inv-equip">
                  {EQUIP_SLOTS.map((slot) => (
                    <button key={slot} className="equip-btn" title={`装备到${EQUIP_SLOT_ZH[slot]}栏`}
                      disabled={busy} onClick={() => equipItem(it.name, slot)}>
                      {EQUIP_ICONS[slot]}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        </div>
        <div className="abilities">
          {Object.entries(c.abilities).map(([ab, val]) => (
            <div key={ab} className="ability">
              <div className="ab-name">{t(ab)}</div>
              <div className="ab-score">{val}</div>
              <div className="ab-mod">{c.modifiers[ab] >= 0 ? "+" : ""}{c.modifiers[ab]}</div>
            </div>
          ))}
        </div>
        <button className="ghost" onClick={onNewGame}>＋ 新冒险</button>
      </aside>
      <main className="chat">
        {messages.length === 0 && (
          <div className="hint">冒险开始！告诉 DM 你想做什么，例如：「我环顾四周，看看酒馆里有什么值得注意的人」</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content}
            {m.role === "assistant" && m.content === "" && "…"}
          </div>
        ))}
        <div ref={bottomRef} />
      </main>
      <footer className="input-bar">
        <div className="quick-actions">
          <button onClick={() => openModal("quests")} disabled={busy} title="告示栏与待办"
            className={hasQuestNotice ? "notice" : ""}>
            📜 任务{hasQuestNotice ? `·${availableQuests.length}` : ""}
          </button>
          <button onClick={() => openModal("shop")} disabled={busy || !hasShop}
            title={hasShop ? `商店（${curLoc?.name}，${shopLevel} 级商货）` : "当前区域没有商店，去集市/城镇看看"}>
            🏪 商店{!hasShop ? "🔒" : ""}
          </button>
          <button onClick={() => openModal("map")} disabled={busy} title="世界地图">🌍 地图</button>
          <button onClick={() => openModal("lore")} disabled={busy} title="世界观词条（地理/势力/历史）"
            className={c.lore?.length > 0 ? "notice" : ""}>
            📖 世界书{c.lore?.length > 0 ? `·${c.lore.length}` : ""}
          </button>
          <button onClick={() => openModal("state")} disabled={busy} title="世界状态（主线进度/势力好感）"
            className={Object.keys(c.world_state || {}).length > 0 ? "notice" : ""}>
            🌐 局势{Object.keys(c.world_state || {}).length > 0 ? `·${Object.keys(c.world_state).length}` : ""}
          </button>
          <button onClick={() => openModal("npcs")} disabled={busy} title="认识的角色档案"
            className={c.npcs?.length > 0 ? "notice" : ""}>
            🧑🤝🧑 认识的人{c.npcs?.length > 0 ? `·${c.npcs.length}` : ""}
          </button>
          <button onClick={() => openModal("skills")} disabled={busy} title="查看全部技能">🎯 技能</button>
          <button onClick={() => !busy && sendText("我想掷一个 D20 骰子。")} disabled={busy} title="任何时候都可检定">🎲 掷骰</button>
          <button onClick={() => !busy && sendText("我环顾四周，仔细观察周围的环境。")} disabled={busy || inCombat} title="非战斗时可用（新环境/可疑线索）">🔍 察觉</button>
          <button onClick={() => !busy && sendText("我压低身形，尝试潜行靠近。")} disabled={busy || inCombat} title="非战斗时可用（需视野遮挡）">🕶️ 潜行</button>
          <button onClick={() => !busy && sendText("我拔出武器，攻击最近的敌人！")} disabled={busy || !inCombat} title="仅战斗时可用">⚔️ 攻击</button>
        </div>
        <div className="input-row">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="输入你的行动…"
            disabled={busy}
          />
          <button onClick={send} disabled={busy} className={busy ? "waiting" : ""}>
            {busy ? "DM 构思中…" : "行动"}
          </button>
        </div>
      </footer>
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>
                {modal === "quests" && "📜 任务"}
                {modal === "shop" && "🏪 商店"}
                {modal === "npcs" && "🧑🤝🧑 认识的人"}
                {modal === "map" && "🌍 世界地图"}
                {modal === "lore" && "📖 世界书"}
                {modal === "state" && "🌐 世界局势"}
                {modal === "skills" && "🎯 技能"}
              </h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            {modalMsg && <div className="modal-msg">{modalMsg}</div>}
            {modal === "quests" && (
              <div className="modal-body">
                <h4>📌 告示栏{availableQuests.length === 0 && "（暂无悬赏）"}</h4>
                {availableQuests.map((q, i) => (
                  <div key={`a${i}`} className="modal-item">
                    <div>
                      <b>{q.title}</b>
                      {q.reward && <span className="quest-reward"> 💰 {q.reward}</span>}
                      {q.description && <div className="modal-desc">{q.description}</div>}
                    </div>
                    <button className="modal-btn" onClick={() => acceptQuest(q.title)}>接受</button>
                  </div>
                ))}
                <h4>✅ 待办{todoQuests.length === 0 && "（尚未接受任务）"}</h4>
                {todoQuests.map((q, i) => (
                  <div key={`t${i}`} className="modal-item todo">
                    <div>
                      <b>{q.title}</b>
                      {q.reward && <span className="quest-reward"> 💰 {q.reward}</span>}
                      {q.description && <div className="modal-desc">{q.description}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {modal === "shop" && (
              <div className="modal-body">
                <div className="shop-gold">💰 金币：{c.gold ?? 0} · 📍 {curLoc?.name || ""}（{shopLevel} 级商货）</div>
                {shopItems.filter((it) => it.level <= shopLevel).map((it, i) => (
                  <div key={i} className="modal-item">
                    <div>
                      <b>{it.name}</b> <span className="shop-price">{it.price} 金币</span>
                      <div className="modal-desc">{it.desc}</div>
                    </div>
                    <button className="modal-btn" onClick={() => buyItem(it.name)}
                      disabled={buying || (c.gold ?? 0) < it.price}>{buying ? "购买中…" : "购买"}</button>
                  </div>
                ))}
              </div>
            )}
            {modal === "state" && (
              <div className="modal-body">
                {!Object.keys(c.world_state || {}).length && <p className="modal-empty">世界局势平静——主线推进、势力态度变化时 DM 会自动更新这里。</p>}
                {Object.entries(c.world_state || {}).map(([k, v]) => (
                  <div key={k} className="modal-item">
                    <div>
                      <b>{k}</b>
                      <div className="modal-desc">📌 {v.value || ""}</div>
                      {v.description && <div className="modal-desc lore-kw">💬 {v.description}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {modal === "lore" && (
              <div className="modal-body">
                {!c.lore?.length && <p className="modal-empty">世界书还是空的——探索中 DM 会自动记录地理、势力、历史等重要设定。</p>}
                {(c.lore || []).map((e, i) => (
                  <div key={i} className="modal-item">
                    <div>
                      <b>{e.title}</b> <span className={`lore-cat ${e.category}`}>{LORE_CAT_ZH[e.category] || e.category}</span>
                      <div className="modal-desc">{e.content}</div>
                      {e.keywords?.length > 0 && (
                        <div className="modal-desc lore-kw">🔑 {e.keywords.join("、")}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {modal === "map" && (
              <div className="modal-body">
                <p className="modal-empty">当前：📍 {curLoc?.name || "未知"}{curLoc?.desc ? `——${curLoc.desc}` : ""}</p>
                {Object.entries(worldMap).map(([key, loc]) => {
                  const here = key === c.location;
                  const reachable = (curLoc?.neighbors || []).includes(key);
                  return (
                    <div key={key} className={`modal-item map-row ${here ? "here" : ""}`}>
                      <div>
                        <b>{loc.name}</b>
                        {loc.shop_level > 0 && <span className="shop-price"> 🏪{loc.shop_level}级</span>}
                        {here && <span className="map-tag here-tag">📍 当前</span>}
                        {!here && reachable && <span className="map-tag">🛤️ 可前往</span>}
                        {!here && !reachable && <span className="map-tag far">非邻接</span>}
                        <div className="modal-desc">{loc.desc}</div>
                      </div>
                      {reachable && !here && (
                        <button className="modal-btn"
                          onClick={() => { setModal(null); sendText(`我前往【${loc.name}】。`); }}>
                          前往
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {modal === "npcs" && (
              <div className="modal-body">
                {!c.npcs?.length && <p className="modal-empty">还没有认识的人——遇到有名字的角色时，DM 会自动记录他们的档案。</p>}
                {(c.npcs || []).map((n, i) => (
                  <div key={i} className="modal-item">
                    <div>
                      <b>{n.name}</b>
                      {n.identity && <span className="npc-identity"> · {n.identity}</span>}
                      <span className={`npc-rel ${n.relationship || "陌生"}`}>{n.relationship || "陌生"}</span>
                      {n.location && <div className="modal-desc">📍 {n.location}</div>}
                      {n.notes && <div className="modal-desc">💬 {n.notes}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {modal === "skills" && (
              <div className="modal-body skills-grid">
                {Object.entries(c.skills).map(([sk, val]) => (
                  <button key={sk} className="modal-skill" title={SKILL_HINTS[sk] || ""}
                    onClick={() => {
                      setModal(null);
                      sendText(`我想过个【${t(sk)}】检定（${SKILL_HINTS[sk] || ""}），看看能发现什么`);
                    }}>
                    <span className={c.proficient_skills?.includes(sk) ? "prof" : ""}>
                      {t(sk)}{c.proficient_skills?.includes(sk) ? "✓" : ""}
                    </span>
                    <small>{SKILL_HINTS[sk] || ""}</small>
                    <em className={val >= 0 ? "pos" : "neg"}>{val >= 0 ? "+" : ""}{val}</em>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
