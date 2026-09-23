import { useMemo, useState } from "react";
import { EmptyState, SourceCard, StatusBanner } from "../../shared/components";
import {
  AFFAIRS_DATASET_KIND,
  AFFAIRS_DATA_VERSION,
  entryDisplayState,
  entrySources,
  filterAffairs,
  listAffairs,
  listCategories,
  todayISO,
} from "./data";
import { CATEGORY_LABELS, type AffairEntry } from "./types";

const CAMPUSES = ["八里台", "津南"];

function TriStateLabel({ value, label }: { value: string; label: string }) {
  const text = value === "yes" ? "需要" : value === "no" ? "不需要" : "未知";
  return (
    <span className="tag">
      {label}：{text}
    </span>
  );
}

function AffairCard({ entry, today }: { entry: AffairEntry; today: string }) {
  const state = entryDisplayState(entry, today);
  return (
    <article className="card">
      <h3>{entry.title}</h3>
      <p>
        <span className="tag">{CATEGORY_LABELS[entry.category] ?? entry.category}</span>
        <span className="tag">{entry.kind === "entry" ? "入口" : "办事流程"}</span>
        {entry.campusScope.length > 0 ? (
          <span className="tag">校区：{entry.campusScope.join(" / ")}</span>
        ) : (
          <span className="tag">校区：通用</span>
        )}
        {entry.audience.length > 0 ? (
          <span className="tag">适用：{entry.audience.join(" / ")}</span>
        ) : null}
        <TriStateLabel value={entry.loginRequired} label="登录" />
        <TriStateLabel value={entry.campusNetworkRequired} label="校园网" />
      </p>
      {state === "expired" ? (
        <StatusBanner
          kind="error"
          message={`该规则按来源记录已于 ${entry.validUntil ?? "未知时间"} 失效，仅供参考，请以最新官方通知为准。`}
        />
      ) : null}
      {state === "needs_verification" ? (
        <StatusBanner
          kind="unverified"
          message="本条为待核验的演示模板，不是学校正式规定；正式来源核验前请勿按此操作。"
        />
      ) : null}
      {entry.steps.length > 0 ? (
        <ol>
          {entry.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : (
        <p className="state__hint">办理步骤：待正式来源核验后补充。</p>
      )}
      {entry.requiredMaterials.length > 0 ? (
        <p>所需材料：{entry.requiredMaterials.join("、")}</p>
      ) : null}
      <div>
        {(() => {
          const sources = entrySources(entry);
          return sources.length > 0 ? (
            sources.map((s) => (
              <SourceCard
                key={s.label}
                source={{
                  label: s.label,
                  href: s.href,
                  locator: s.locator,
                  verifiedAt: s.verifiedAt,
                }}
              />
            ))
          ) : (
            <SourceCard source={{ label: "暂无正式来源", verifiedAt: undefined }} />
          );
        })()}
        {entry.validUntil ? (
          <p className="state__hint">有效期至：{entry.validUntil}</p>
        ) : null}
      </div>
    </article>
  );
}

/** 校园事务页：分类搜索、来源展示、适用范围、登录/校园网限制、步骤与过期/待核验提示。 */
export function AffairsPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [campus, setCampus] = useState("");
  const today = todayISO();
  const all = useMemo(() => listAffairs(), []);
  const filtered = useMemo(
    () => filterAffairs(all, { query, category, campus }),
    [all, query, category, campus]
  );

  return (
    <section>
      <h2>校园事务</h2>
      <StatusBanner
        kind="demo"
        message={`当前数据为虚构演示集（${AFFAIRS_DATASET_KIND} / ${AFFAIRS_DATA_VERSION}），正式来源核验完成前不代表学校规定。`}
      />
      <div className="toolbar">
        <input
          type="search"
          placeholder="搜索事务或步骤…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="搜索事务"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="按分类筛选"
        >
          <option value="">全部分类</option>
          {listCategories().map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c] ?? c}
            </option>
          ))}
        </select>
        <select
          value={campus}
          onChange={(e) => setCampus(e.target.value)}
          aria-label="按校区筛选"
        >
          <option value="">全部校区</option>
          {CAMPUSES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      {filtered.length === 0 ? (
        <EmptyState title="没有匹配的事务" hint="换个关键词或分类试试。" />
      ) : (
        filtered.map((entry) => (
          <AffairCard key={entry.entryId} entry={entry} today={today} />
        ))
      )}
    </section>
  );
}
