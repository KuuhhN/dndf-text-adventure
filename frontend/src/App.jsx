import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

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
    // 自动触发 DM 开场
    setTimeout(() => sendText("冒险开始！请描绘酒馆场景，介绍我面前的机会。"), 100);
  }

  async function sendText(text) {
    if (!text.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const resp = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session.id, message: text }),
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
          const d = await (await fetch(`${API}/api/session/${session.id}`)).json();
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

function CreateWizard({ races, classes, onSubmit }) {
  const [form, setForm] = useState({ name: "", race: "", class_name: "", method: "standard", chosen_skills: [] });
  const [skillChoices, setSkillChoices] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function onClassChange(e) {
    const cls = e.target.value;
    setForm({ ...form, class_name: cls, chosen_skills: [] });
    if (!cls) {
      setSkillChoices(null);
      return;
    }
    const resp = await fetch(`${API}/api/class/${cls}/skill-choices`);
    const d = await resp.json();
    setSkillChoices(d.choose ? d : null);
  }

  function toggleSkill(skill) {
    const picked = form.chosen_skills.includes(skill)
      ? form.chosen_skills.filter((s) => s !== skill)
      : [...form.chosen_skills, skill].slice(0, skillChoices.choose);
    setForm({ ...form, chosen_skills: picked });
  }

  const ready = form.name && form.race && form.class_name;
  return (
    <div className="wizard">
      <h1>🗡️ DNDF 文字冒险</h1>
      <p className="sub">创建你的冒险者，AI 地下城主将为你编织传奇</p>
      <label>角色名
        <input value={form.name} onChange={set("name")} placeholder="例如：铁锤·铜须" />
      </label>
      <label>种族
        <select value={form.race} onChange={set("race")}>
          <option value="">选择种族…</option>
          {races.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </label>
      <label>职业
        <select value={form.class_name} onChange={onClassChange}>
          <option value="">选择职业…</option>
          {classes.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      {skillChoices && (
        <div className="skill-pick">
          <div className="skill-pick-title">
            选择熟练技能（选 {skillChoices.choose} 个）
          </div>
          <div className="skill-pick-opts">
            {skillChoices.options.map((s) => (
              <label key={s} className={`chip ${form.chosen_skills.includes(s) ? "on" : ""}`}>
                <input
                  type="checkbox"
                  checked={form.chosen_skills.includes(s)}
                  onChange={() => toggleSkill(s)}
                />
                {s}
              </label>
            ))}
          </div>
        </div>
      )}
      <label>属性生成
        <select value={form.method} onChange={set("method")}>
          <option value="standard">标准购点（15,14,13,12,10,8）</option>
          <option value="rolled">骰点（4d6 取 3 高）</option>
        </select>
      </label>
      <button className="primary" disabled={!ready} onClick={() => onSubmit(form)}>
        开始冒险
      </button>
    </div>
  );
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
            {c.race} {c.class} · Lv.{c.level}
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
                  <span>{e.name}</span>
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
        </div>
        <div className="abilities">
          {Object.entries(c.abilities).map(([ab, val]) => (
            <div key={ab} className="ability">
              <div className="ab-name">{ab}</div>
              <div className="ab-score">{val}</div>
              <div className="ab-mod">{c.modifiers[ab] >= 0 ? "+" : ""}{c.modifiers[ab]}</div>
            </div>
          ))}
        </div>
        <div className="skills">
          <h3>技能</h3>
          {Object.entries(c.skills).map(([sk, val]) => (
            <div key={sk} className="skill">
              <span>{sk}</span>
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
          <button onClick={send} disabled={busy}>{busy ? "…" : "行动"}</button>
        </div>
      </footer>
    </div>
  );
}

export default App;
