import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

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
};
const t = (k) => ZH[k] || k; // 未知名称回退英文

function App() {
  const [races, setRaces] = useState([]);
  const [classes, setClasses] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState(null); // {id, character, history}
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
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
      alert(d.error || "创建失败");
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
        const evt = JSON.parse(payload);
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
        } else if (evt.type === "error") {
          setMessages((prev) => [...prev, { role: "error", content: evt.text }]);
        }
      }
    }
    setBusy(false);
  }

  function send() {
    sendText(input);
  }

  return (
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
          setInput={setInput}
          send={send}
          sendText={sendText}
          bottomRef={bottomRef}
          onNewGame={() => setSession(null)}
        />
      )}
    </div>
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
    chosen_skills: [], background: "", feat: "",
  });
  const [raceDetail, setRaceDetail] = useState(null);
  const [classDetail, setClassDetail] = useState(null);
  const [feats, setFeats] = useState([]);
  const [backgrounds, setBackgrounds] = useState([]);
  const [rolled, setRolled] = useState(null);
  const set = (k, v) => setForm({ ...form, [k]: v });

  async function pickRace(name) {
    set("race", name);
    const d = await (await fetch(`${API}/api/races/${name}`)).json();
    setRaceDetail(d);
  }
  async function pickClass(name) {
    set("class_name", name);
    set("chosen_skills", []);
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

  const canNext =
    (step === 1 && form.race) || (step === 2 && form.class_name) ||
    (step === 3 && (form.method === "rolled" ? rolled : spent() <= PB_BUDGET)) ||
    (step === 4 && form.chosen_skills.length === (classDetail?.skill_choices?.choose ?? 0)) ||
    (step === 5 && form.background) || (step === 6 && form.name.trim());

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
  const steps = ["种族", "职业", "属性", "技能", "专长·背景", "名字"];

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
                    体型 {t(raceDetail.size)} · 速度 {raceDetail.speed}ft
                    {raceDetail.ability_bonuses.length > 0 && (
                      <> · 加成 {raceDetail.ability_bonuses.map((b) => `${t(b.ability)}+${b.bonus}`).join(" ")}</>
                    )}
                  </div>
                  <ul className="detail-traits">
                    {raceDetail.traits.map((tr) => (
                      <li key={tr.index}>
                        <b>{t(tr.name)}</b>
                        <p>{tr.desc}</p>
                      </li>
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
                  <ul className="detail-traits">
                    {Object.entries(classDetail.level_features).flatMap(([lv, feats]) =>
                      feats.map((f) => (
                        <li key={`${lv}-${f.index}`}>
                          <b>{t(f.name)}</b>
                          <p>{f.desc}</p>
                        </li>
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
                      修正 {mod(totalMod[ab])} <small>（含种族 {mod(totalMod[ab] - base)}）</small>
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
          <div className="skill-pick big">
            <div className="skill-pick-title">
              选择熟练技能（选 {classDetail?.skill_choices?.choose ?? 0} 个）
            </div>
            <div className="skill-pick-opts">
              {(classDetail?.skill_choices?.options ?? []).map((s) => (
                <label key={s} className={`chip ${form.chosen_skills.includes(s) ? "on" : ""}`}>
                  <input
                    type="checkbox"
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
            <p className="pb-note">背景也会提供额外技能熟练（下一步选择）。</p>
          </div>
        )}

        {step === 5 && (
          <div className="feat-panel">
            <h3>背景（提供技能熟练 + 专长）</h3>
            <div className="bg-list">
              {backgrounds.map((b) => (
                <button key={b.index} className={`bg-card ${form.background === b.name ? "on" : ""}`} onClick={() => set("background", b.name)}>
                  <b>{t(b.name)}</b>
                  <span>赠送专长：{t(b.feat)}</span>
                  <span>技能：{b.proficiencies.map((p) => t(p.replace("Skill: ", ""))).join("、")}</span>
                </button>
              ))}
            </div>
            <h3>1 级专长（可选）</h3>
            <div className="bg-list">
              {feats.map((f) => (
                <button key={f.index} className={`bg-card ${form.feat === f.name ? "on" : ""}`} onClick={() => set("feat", form.feat === f.name ? "" : f.name)}>
                  <b>{t(f.name)}</b>
                  <span>{f.desc.slice(0, 60)}…</span>
                </button>
              ))}
            </div>
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
          <button className="primary" disabled={!canNext} onClick={next}>下一步 →</button>
        ) : (
          <button className="primary" disabled={!canNext} onClick={() => onSubmit(form)}>开始冒险</button>
        )}
      </div>
    </div>
  );
}

function mod(v) {
  return v >= 0 ? `+${v}` : `${v}`;
}

function formatTool(evt) {
  const r = evt.result;
  if (r.error) return `⚠️ ${r.error}`;
  switch (evt.call.name) {
    case "roll_dice":
      return `🎲 掷 ${r.expression}：${r.rolls.join(" + ")}${r.total !== r.rolls[0] ? ` = ${r.total}` : ""}${r.crit ? "  💥重击！" : ""}${r.fumble ? "  💀失手！" : ""}`;
    case "ability_check":
      return `🎯 ${r.label}：D20 ${r.d20} + ${r.modifier} = ${r.total}${r.crit ? "  💥大成功！" : ""}${r.fumble ? "  💀大失败！" : ""}`;
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
    default:
      return JSON.stringify(r);
  }
}

function GameView({ character, messages, input, busy, setInput, send, sendText, bottomRef, onNewGame }) {
  const c = character;
  return (
    <div className="game">
      <aside className="sheet">
        <div className="sheet-head">
          <h2>{c.name}</h2>
          <div className="meta">
            {t(c.race)} {t(c.class)} · Lv.{c.level}
          </div>
          <div className="bars">
            <div className="bar">❤️ HP {c.current_hp}/{c.max_hp} · Lv.{c.level} · XP {c.xp}</div>
            <div className="bar">🛡️ AC {c.ac} · ⚡ {c.speed}ft · 熟练 +{c.proficiency_bonus}</div>
          </div>
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
        {c.quests?.length > 0 && (
          <div className="quest-board">
            <h3>📜 任务告示</h3>
            {c.quests.map((q, i) => (
              <div key={i} className={`quest-note ${q.status === "accepted" ? "accepted" : ""}`}>
                <div className="pin" />
                <div className="quest-title">{q.title}</div>
                {q.reward && <span className="quest-reward">💰 {q.reward}</span>}
                {q.description && <div className="quest-desc">{q.description}</div>}
                <span className={`quest-status ${q.status}`}>
                  {q.status === "accepted" ? "已接下" : "悬赏中"}
                </span>
              </div>
            ))}
          </div>
        )}
        {c.inventory?.length > 0 && (
          <div className="inventory">
            <h3>🎒 背包</h3>
            {c.inventory.map((it, i) => (
              <div key={i} className="inv-item" title={it.description || ""}>
                <span className="inv-name">{it.name}</span>
                {it.quantity > 1 && <span className="inv-qty">×{it.quantity}</span>}
                {it.description && <span className="inv-desc">{it.description}</span>}
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
        <div className="skills">
          <h3>技能</h3>
          {Object.entries(c.skills).map(([sk, val]) => (
            <div key={sk} className="skill">
              <span>{t(sk)}</span>
              <span className={val >= 0 ? "pos" : "neg"}>{val >= 0 ? "+" : ""}{val}</span>
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
          <button onClick={() => !busy && sendText("我想掷一个 D20 骰子。")} disabled={busy}>🎲 掷骰</button>
          <button onClick={() => !busy && sendText("我环顾四周，仔细观察周围的环境。")} disabled={busy}>🔍 察觉</button>
          <button onClick={() => !busy && sendText("我压低身形，尝试潜行靠近。")} disabled={busy}>🕶️ 潜行</button>
          <button onClick={() => !busy && sendText("我拔出武器，攻击最近的敌人！")} disabled={busy}>⚔️ 攻击</button>
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
    </div>
  );
}

export default App;
