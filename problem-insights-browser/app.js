(function () {
  "use strict";

  const rawData = window.CF_INSIGHTS_DATA || { summary: {}, contests: [], topics: [], columns: [] };
  const ACCOUNT_HANDLES_KEY = "cf-insights-account-handles-v1";
  const ACCOUNT_CACHE_KEY = "cf-insights-account-cache-v2";
  const LEGACY_ACCOUNT_CACHE_KEY = "cf-insights-account-cache-v1";
  const CF_STATUS_ENDPOINT = "https://codeforces.com/api/user.status";
  const STATUS_PAGE_SIZE = 10000;
  const state = {
    topic: "all",
    minRating: "",
    maxRating: "",
    hasEditorial: false,
    unsolvedOnly: false,
    contestType: "all",
    sort: "date-desc",
    view: "contests",
    selectedKey: "",
    accountHandles: loadAccountHandles(),
    accountCache: loadAccountCache(),
    accountSyncing: false,
    accountMessage: "",
  };

  const elements = {
    topicSelect: document.getElementById("topicSelect"),
    minRatingInput: document.getElementById("minRatingInput"),
    maxRatingInput: document.getElementById("maxRatingInput"),
    hasEditorialCheckbox: document.getElementById("hasEditorialCheckbox"),
    unsolvedOnlyCheckbox: document.getElementById("unsolvedOnlyCheckbox"),
    contestTypes: document.getElementById("contestTypes"),
    randomButton: document.getElementById("randomButton"),
    sortSelect: document.getElementById("sortSelect"),
    resultTitle: document.getElementById("resultTitle"),
    resultSubtitle: document.getElementById("resultSubtitle"),
    contestTable: document.getElementById("contestTable"),
    detailPanel: document.getElementById("detailPanel"),
    accountsButton: document.getElementById("accountsButton"),
    accountsDialog: document.getElementById("accountsDialog"),
    accountHandleInput: document.getElementById("accountHandleInput"),
    accountList: document.getElementById("accountList"),
    accountStatus: document.getElementById("accountStatus"),
    addAccountButton: document.getElementById("addAccountButton"),
    syncAccountsButton: document.getElementById("syncAccountsButton"),
    closeAccountsButton: document.getElementById("closeAccountsButton"),
    navButtons: Array.from(document.querySelectorAll(".nav-button")),
  };

  const allProblems = rawData.contests.flatMap((contest) =>
    contest.problems.map((problem) => ({
      ...problem,
      contestId: contest.id,
      contestName: contest.name,
      contestDate: contest.date,
      contestType: contest.type,
      contestUrl: contest.url,
    }))
  );

  const problemByKey = new Map(allProblems.map((problem) => [problem.key, problem]));
  const topicRank = new Map((rawData.topics || []).map((topic, index) => [topic, index]));
  const localProblemKeys = new Set(allProblems.map((problem) => problem.key));

  function normalizedProblemTitle(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function contestFamilyKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\s*\(\s*div\.\s*[12][^)]*\)/gi, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  const contestFamilyById = new Map(
    (rawData.contests || []).map((contest) => [String(contest.id), contestFamilyKey(contest.name)]),
  );
  const equivalentProblemKeysBySignature = new Map();
  for (const problem of allProblems) {
    const signature = `${contestFamilyKey(problem.contestName)}|${normalizedProblemTitle(problem.title)}`;
    const keys = equivalentProblemKeysBySignature.get(signature) || new Set();
    keys.add(problem.key);
    equivalentProblemKeysBySignature.set(signature, keys);
  }
  const equivalentProblemKeysByKey = new Map();
  for (const keys of equivalentProblemKeysBySignature.values()) {
    if (keys.size < 2) continue;
    for (const key of keys) equivalentProblemKeysByKey.set(key, keys);
  }

  function loadLocalJson(key, fallback) {
    try {
      const value = window.localStorage.getItem(key);
      return value ? JSON.parse(value) : fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function saveLocalJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (_error) {
      state.accountMessage = "浏览器无法保存账号缓存，请检查隐私模式或存储权限。";
    }
  }

  function normalizeHandle(value) {
    return String(value || "").trim().replace(/\s+/g, "");
  }

  function handleKey(handle) {
    return normalizeHandle(handle).toLowerCase();
  }

  function loadAccountHandles() {
    const value = loadLocalJson(ACCOUNT_HANDLES_KEY, []);
    if (!Array.isArray(value)) return [];
    const unique = new Map();
    for (const raw of value) {
      const handle = normalizeHandle(raw);
      if (handle) unique.set(handleKey(handle), handle);
    }
    return Array.from(unique.values());
  }

  function loadAccountCache() {
    const value = loadLocalJson(ACCOUNT_CACHE_KEY, null);
    if (value && typeof value === "object" && !Array.isArray(value)) return value;
    const legacyValue = loadLocalJson(LEGACY_ACCOUNT_CACHE_KEY, {});
    return legacyValue && typeof legacyValue === "object" && !Array.isArray(legacyValue) ? legacyValue : {};
  }

  function saveAccountState() {
    saveLocalJson(ACCOUNT_HANDLES_KEY, state.accountHandles);
    saveLocalJson(ACCOUNT_CACHE_KEY, state.accountCache);
  }

  function solvedHandlesFor(problemKey) {
    const equivalentKeys = equivalentProblemKeysByKey.get(problemKey) || new Set([problemKey]);
    return state.accountHandles.filter((handle) => {
      const entry = state.accountCache[handleKey(handle)];
      return entry
        && Array.isArray(entry.acceptedKeys)
        && entry.acceptedKeys.some((acceptedKey) => equivalentKeys.has(acceptedKey));
    });
  }

  function accountSummaryText() {
    const solvedCount = allProblems.filter((problem) => solvedHandlesFor(problem.key).length > 0).length;
    if (!state.accountHandles.length) return "绑定账号";
    return `账号 ${state.accountHandles.length} · 已过 ${solvedCount}`;
  }

  function sleep(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  async function fetchAcceptedProblems(handle) {
    const acceptedKeys = new Set();
    let from = 1;
    let submissionCount = 0;
    while (true) {
      if (from > 1) await sleep(2100);
      const params = new URLSearchParams({
        handle,
        from: String(from),
        count: String(STATUS_PAGE_SIZE),
      });
      const response = await fetch(`${CF_STATUS_ENDPOINT}?${params.toString()}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.status !== "OK") {
        const message = payload.comment || `HTTP ${response.status}`;
        throw new Error(message);
      }
      const submissions = Array.isArray(payload.result) ? payload.result : [];
      submissionCount += submissions.length;
      for (const submission of submissions) {
        if (submission.verdict !== "OK") continue;
        const problem = submission.problem || {};
        const contestId = problem.contestId || submission.contestId || "";
        const key = `${contestId}${problem.index || ""}`;
        if (localProblemKeys.has(key)) acceptedKeys.add(key);
        const family = contestFamilyById.get(String(contestId));
        const title = normalizedProblemTitle(problem.name);
        if (!family || !title) continue;
        const equivalentKeys = equivalentProblemKeysBySignature.get(`${family}|${title}`);
        if (equivalentKeys) {
          for (const equivalentKey of equivalentKeys) acceptedKeys.add(equivalentKey);
        }
      }
      if (submissions.length < STATUS_PAGE_SIZE) break;
      from += STATUS_PAGE_SIZE;
    }
    return {
      handle,
      fetchedAt: new Date().toISOString(),
      acceptedKeys: Array.from(acceptedKeys).sort(),
      submissionCount,
    };
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderMath(root) {
    if (typeof window.renderMathInElement !== "function") return;
    window.renderMathInElement(root, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "\\(", right: "\\)", display: false },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false,
      strict: "ignore",
    });
  }

  function ratingClass(rating) {
    if (!Number.isFinite(rating)) return "rating-gray";
    if (rating < 1200) return "rating-gray";
    if (rating < 1400) return "rating-green";
    if (rating < 1600) return "rating-cyan";
    if (rating < 1900) return "rating-blue";
    if (rating < 2100) return "rating-violet";
    if (rating < 2400) return "rating-orange";
    return "rating-red";
  }

  function hasSolution(problem) {
    return problem.extractionStatus !== "missing_editorial";
  }

  function solutionStatusText(problem) {
    return hasSolution(problem) ? "有题解" : "无题解";
  }

  function parseRatingBoundary(value) {
    const text = String(value || "").trim();
    if (!text) return null;
    const rating = Number(text);
    return Number.isFinite(rating) ? rating : null;
  }

  function problemMatches(problem) {
    if (state.topic !== "all" && problem.primaryTopic !== state.topic) return false;
    if (state.hasEditorial && !hasSolution(problem)) return false;
    if (state.unsolvedOnly && solvedHandlesFor(problem.key).length > 0) return false;
    const rating = Number(problem.rating);
    const minRating = parseRatingBoundary(state.minRating);
    const maxRating = parseRatingBoundary(state.maxRating);
    if (minRating !== null && (!Number.isFinite(rating) || rating < minRating)) return false;
    if (maxRating !== null && (!Number.isFinite(rating) || rating > maxRating)) return false;
    return true;
  }

  function visibleContests() {
    const rows = rawData.contests
      .filter((contest) => state.contestType === "all" || contest.type === state.contestType)
      .map((contest) => ({
        ...contest,
        problems: contest.problems.filter(problemMatches),
      }))
      .filter((contest) => contest.problems.length > 0);

    rows.sort((left, right) => {
      if (state.sort === "date-asc") return left.date.localeCompare(right.date) || left.id - right.id;
      if (state.sort === "max-rating") return Number(right.maxRating || 0) - Number(left.maxRating || 0) || right.id - left.id;
      if (state.sort === "problem-count") return right.problems.length - left.problems.length || right.id - left.id;
      return right.date.localeCompare(left.date) || right.id - left.id;
    });
    return rows;
  }

  function visibleProblems() {
    return allProblems.filter(problemMatches);
  }

  function renderAccountControls() {
    if (!elements.accountsButton) return;
    elements.accountsButton.textContent = accountSummaryText();
    if (!elements.accountList) return;
    if (!state.accountHandles.length) {
      elements.accountList.innerHTML = '<div class="account-empty">还没有绑定账号。</div>';
    } else {
      elements.accountList.innerHTML = state.accountHandles
        .map((handle) => {
          const entry = state.accountCache[handleKey(handle)];
          const synced = entry && entry.fetchedAt ? `同步于 ${new Date(entry.fetchedAt).toLocaleString()}` : "尚未同步";
          const count = entry && Array.isArray(entry.acceptedKeys) ? entry.acceptedKeys.length : 0;
          return `
            <div class="account-item">
              <div>
                <strong>${escapeHtml(handle)}</strong>
                <span>${escapeHtml(`${synced} · 本地已过 ${count} 题`)}</span>
              </div>
              <button type="button" class="account-remove" data-remove-account="${escapeHtml(handle)}">移除</button>
            </div>
          `;
        })
        .join("");
    }
    elements.accountStatus.textContent = state.accountMessage;
    elements.syncAccountsButton.disabled = state.accountSyncing || !state.accountHandles.length;
    elements.addAccountButton.disabled = state.accountSyncing;
  }

  async function syncAccounts() {
    if (!state.accountHandles.length || state.accountSyncing) return;
    state.accountSyncing = true;
    state.accountMessage = "正在从 Codeforces 同步通过记录……";
    renderAccountControls();
    render();
    const failures = [];
    for (const handle of state.accountHandles) {
      state.accountMessage = `正在同步 ${handle}……`;
      renderAccountControls();
      try {
        state.accountCache[handleKey(handle)] = await fetchAcceptedProblems(handle);
        saveAccountState();
      } catch (error) {
        failures.push(`${handle}: ${error instanceof Error ? error.message : "同步失败"}`);
      }
    }
    state.accountSyncing = false;
    state.accountMessage = failures.length
      ? `部分账号同步失败：${failures.join("；")}`
      : `同步完成：已检查 ${state.accountHandles.length} 个账号。`;
    saveAccountState();
    renderAccountControls();
    render();
  }

  function renderControls() {
    elements.topicSelect.innerHTML = [
      '<option value="all">全部</option>',
      ...rawData.topics.map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)} (${escapeHtml(rawData.topicCounts[topic] || 0)})</option>`),
    ].join("");
    elements.topicSelect.value = state.topic;
    elements.minRatingInput.value = state.minRating;
    elements.maxRatingInput.value = state.maxRating;
    elements.hasEditorialCheckbox.checked = state.hasEditorial;
    elements.unsolvedOnlyCheckbox.checked = state.unsolvedOnly;
    const typeCounts = new Map();
    for (const contest of rawData.contests) typeCounts.set(contest.type, (typeCounts.get(contest.type) || 0) + 1);
    const items = [{ type: "all", label: "全部", count: rawData.contests.length }].concat(
      rawData.contestTypes.map((type) => ({ type, label: type, count: typeCounts.get(type) || 0 })).filter((item) => item.count > 0),
    );
    elements.contestTypes.innerHTML = items
      .map(
        (item) => `
          <button class="type-button ${state.contestType === item.type ? "is-active" : ""}" type="button" data-type="${escapeHtml(item.type)}">
            ${escapeHtml(item.label)}<span class="count-pill">${escapeHtml(item.count)}</span>
          </button>
        `,
      )
      .join("");
  }

  function renderContestView() {
    const rows = visibleContests();
    const problemCount = rows.reduce((sum, contest) => sum + contest.problems.length, 0);
    elements.resultTitle.textContent = "Contests";
    elements.resultSubtitle.textContent = `Showing ${problemCount} of ${allProblems.length} problems in ${rows.length} contests`;
    elements.contestTable.style.display = "";
    if (!rows.length) {
      elements.contestTable.innerHTML = '<tbody><tr><td class="empty-state">没有匹配的题目。</td></tr></tbody>';
      renderDetail();
      return;
    }

    if (!problemByKey.has(state.selectedKey) || !visibleProblems().some((problem) => problem.key === state.selectedKey)) {
      state.selectedKey = rows[0].problems[0].key;
    }

    const columns = rawData.columns || ["A", "B", "C", "D", "E", "F", "G", "H", "I"];
    const head = `
      <thead>
        <tr>
          <th class="rank-head">#</th>
          <th class="contest-head">Contest</th>
          ${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}
        </tr>
      </thead>
    `;
    const body = rows
      .map((contest, rowIndex) => {
        const bySlot = new Map();
        for (const problem of contest.problems) {
          if (!bySlot.has(problem.slot)) bySlot.set(problem.slot, []);
          bySlot.get(problem.slot).push(problem);
        }
        return `
          <tr>
            <td class="rank-cell">${rowIndex + 1}</td>
            <td class="contest-cell">
              <a class="contest-name" href="${escapeHtml(contest.url)}" target="_blank" rel="noreferrer">CF ${escapeHtml(contest.id)}</a>
              <div>${escapeHtml(contest.name)}</div>
              <div class="contest-meta">${escapeHtml(contest.date || "无日期")} · ${escapeHtml(contest.type)} · ${escapeHtml(contest.problemCount)} 题</div>
            </td>
            ${columns.map((column) => `<td class="problem-cell">${renderProblemStack(bySlot.get(column) || [])}</td>`).join("")}
          </tr>
        `;
      })
      .join("");
    elements.contestTable.innerHTML = head + `<tbody>${body}</tbody>`;
    renderDetail();
  }

  function renderProblemStack(problems) {
    if (!problems.length) return "";
    return `
      <div class="problem-stack">
        ${problems
          .map((problem) => {
            const full = problemByKey.get(problem.key) || problem;
            const solvedHandles = solvedHandlesFor(problem.key);
            const solved = solvedHandles.length > 0;
            const solvedLabel = solvedHandles.length > 1 ? `已过 ${solvedHandles.length} 个账号` : "已通过";
            return `
              <button class="problem-chip ${state.selectedKey === problem.key ? "is-active" : ""} ${problem.extractionStatus === "missing_editorial" ? "is-missing" : ""} ${solved ? "is-solved" : ""}"
                type="button" data-problem-key="${escapeHtml(problem.key)}" title="${escapeHtml(problem.title)}">
                <div class="chip-head"><span><span class="chip-index">${escapeHtml(problem.index)}</span> <span class="${ratingClass(problem.rating)}">${escapeHtml(problem.rating || "N/A")}</span></span>${solved ? `<span class="solved-badge">${escapeHtml(solvedLabel)}</span>` : ""}</div>
                <div class="chip-title ${ratingClass(problem.rating)}">${escapeHtml(problem.title)}</div>
                <div class="chip-meta"><span>${escapeHtml(full.primaryTopic)}</span><span>${escapeHtml(solutionStatusText(problem))}</span></div>
              </button>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderTopicsView() {
    const problems = visibleProblems().slice().sort((left, right) => {
      const rank = (topicRank.get(left.primaryTopic) ?? 999) - (topicRank.get(right.primaryTopic) ?? 999);
      return rank || Number(right.rating || 0) - Number(left.rating || 0) || left.key.localeCompare(right.key);
    });
    elements.resultTitle.textContent = "Topics";
    elements.resultSubtitle.textContent = `Showing ${problems.length} of ${allProblems.length} problems`;
    const groups = new Map();
    for (const problem of problems) {
      if (!groups.has(problem.primaryTopic)) groups.set(problem.primaryTopic, []);
      groups.get(problem.primaryTopic).push(problem);
    }
    if (!problems.length) {
      elements.contestTable.innerHTML = '<tbody><tr><td class="empty-state">没有匹配的题目。</td></tr></tbody>';
      renderDetail();
      return;
    }
    const html = `
      <tbody><tr><td class="topic-view">
        ${Array.from(groups.entries())
          .map(
            ([topic, items]) => `
              <section class="topic-block">
                <h2>${escapeHtml(topic)} <span class="count-pill">${escapeHtml(items.length)}</span></h2>
                <div class="topic-problems">
                  ${items
                    .map((problem) => {
                      const solved = solvedHandlesFor(problem.key).length > 0;
                      return `<button type="button" class="${solved ? "is-solved" : ""}" data-problem-key="${escapeHtml(problem.key)}"><span class="${ratingClass(problem.rating)}">${escapeHtml(problem.key)} · ${escapeHtml(problem.title)}</span> · ${escapeHtml(problem.rating || "N/A")}${solved ? ' <span class="solved-inline">已通过</span>' : ""}</button>`;
                    })
                    .join("")}
                </div>
              </section>
            `,
          )
          .join("")}
      </td></tr></tbody>
    `;
    elements.contestTable.innerHTML = html;
    if (!problemByKey.has(state.selectedKey) || !problems.some((problem) => problem.key === state.selectedKey)) {
      state.selectedKey = problems[0].key;
    }
    renderDetail();
  }

  function renderDetail() {
    const problem = problemByKey.get(state.selectedKey);
    if (!problem) {
      elements.detailPanel.innerHTML = '<div class="detail-empty">选择一道题查看题意、转换和关键观察。</div>';
      return;
    }
    const transformationHtml = problem.transformedStatement
      ? `
        <details class="detail-section detail-disclosure">
          <summary>转换</summary>
          <div class="detail-section-body">
            <p>${escapeHtml(problem.transformedStatement)}</p>
          </div>
        </details>
      `
      : "";
    const observationHtml = problem.keyObservations.length
      ? `
        <section class="detail-section">
          <h3>关键观察</h3>
          <div class="observations">${problem.keyObservations
            .map(
              (item, index) => `
                <details class="observation-hint">
                  <summary>提示 ${index + 1}</summary>
                  <p>${escapeHtml(item)}</p>
                </details>
              `,
            )
            .join("")}</div>
        </section>
      `
      : "";
    const solutionHtml = problem.solutionBrief
      ? `
        <details class="detail-section detail-disclosure">
          <summary>简要题解</summary>
          <div class="detail-section-body">
            <p>${escapeHtml(problem.solutionBrief)}</p>
          </div>
        </details>
      `
      : "";
    const tags = [problem.primaryTopic, ...(problem.secondaryTopics || [])];
    const solvedHandles = solvedHandlesFor(problem.key);
    elements.detailPanel.innerHTML = `
      <article class="detail-content">
        <div class="detail-top">
          <div>
            <h2 class="detail-title">${escapeHtml(problem.key)} · ${escapeHtml(problem.title)}</h2>
            <div class="contest-meta">${escapeHtml(problem.contestName)} · ${escapeHtml(problem.contestDate || "无日期")}</div>
          </div>
          <div class="detail-rating ${ratingClass(problem.rating)}">${escapeHtml(problem.rating || "N/A")}</div>
        </div>
        <div class="detail-links">
          <a href="${escapeHtml(problem.problemUrl)}" target="_blank" rel="noreferrer">原题</a>
          <a href="${escapeHtml(problem.editorialUrl)}" target="_blank" rel="noreferrer">题解</a>
          <a href="${escapeHtml(problem.contestUrl)}" target="_blank" rel="noreferrer">竞赛</a>
        </div>
        <div class="tag-row">
          ${tags.map((tag, index) => `<span class="tag ${index === 0 ? "topic" : ""}">${escapeHtml(tag)}</span>`).join("")}
          <span class="tag ${hasSolution(problem) ? "" : "missing"}">${escapeHtml(solutionStatusText(problem))}</span>
          ${solvedHandles.length ? `<span class="tag solved-tag">${escapeHtml(solvedHandles.length > 1 ? `已通过 ${solvedHandles.length} 个账号` : `已通过 ${solvedHandles[0]}`)}</span>` : ""}
        </div>
        <section class="detail-section">
          <h3>题意</h3>
          <p>${escapeHtml(problem.statementBrief)}</p>
        </section>
        ${transformationHtml}
        ${observationHtml}
        ${solutionHtml}
        <section class="detail-section">
          <h3>原始标签</h3>
          <p>${escapeHtml((problem.originalTags || []).join(", ") || "无")}</p>
        </section>
      </article>
    `;
    renderMath(elements.detailPanel);
  }

  function render() {
    renderControls();
    for (const button of elements.navButtons) {
      button.classList.toggle("is-active", button.dataset.view === state.view);
    }
    if (state.view === "topics") renderTopicsView();
    else renderContestView();
  }

  function bindEvents() {
    elements.topicSelect.addEventListener("change", () => {
      state.topic = elements.topicSelect.value;
      render();
    });
    elements.minRatingInput.addEventListener("input", () => {
      state.minRating = elements.minRatingInput.value;
      render();
    });
    elements.maxRatingInput.addEventListener("input", () => {
      state.maxRating = elements.maxRatingInput.value;
      render();
    });
    elements.hasEditorialCheckbox.addEventListener("change", () => {
      state.hasEditorial = elements.hasEditorialCheckbox.checked;
      render();
    });
    elements.unsolvedOnlyCheckbox.addEventListener("change", () => {
      state.unsolvedOnly = elements.unsolvedOnlyCheckbox.checked;
      render();
    });
    elements.sortSelect.addEventListener("change", () => {
      state.sort = elements.sortSelect.value;
      render();
    });
    elements.contestTypes.addEventListener("click", (event) => {
      const button = event.target.closest("[data-type]");
      if (!button) return;
      state.contestType = button.dataset.type;
      render();
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-problem-key]");
      if (!button) return;
      state.selectedKey = button.dataset.problemKey;
      render();
    });
    elements.randomButton.addEventListener("click", () => {
      const problems = visibleProblems();
      if (!problems.length) return;
      const next = problems[Math.floor(Math.random() * problems.length)];
      state.selectedKey = next.key;
      state.view = "contests";
      render();
    });
    elements.accountsButton?.addEventListener("click", () => {
      renderAccountControls();
      elements.accountsDialog.showModal();
    });
    elements.closeAccountsButton?.addEventListener("click", () => {
      elements.accountsDialog.close();
    });
    elements.addAccountButton?.addEventListener("click", () => {
      const handle = normalizeHandle(elements.accountHandleInput.value);
      if (!handle) {
        state.accountMessage = "请输入 Codeforces handle。";
        renderAccountControls();
        return;
      }
      if (!state.accountHandles.some((item) => handleKey(item) === handleKey(handle))) {
        state.accountHandles.push(handle);
        saveAccountState();
      }
      elements.accountHandleInput.value = "";
      state.accountMessage = `已绑定 ${handle}，点击“同步通过记录”获取状态。`;
      renderAccountControls();
      render();
    });
    elements.accountHandleInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        elements.addAccountButton.click();
      }
    });
    elements.accountList?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-account]");
      if (!button) return;
      const handle = button.dataset.removeAccount;
      state.accountHandles = state.accountHandles.filter((item) => handleKey(item) !== handleKey(handle));
      delete state.accountCache[handleKey(handle)];
      state.accountMessage = `已移除 ${handle}。`;
      saveAccountState();
      renderAccountControls();
      render();
    });
    elements.syncAccountsButton?.addEventListener("click", syncAccounts);
    for (const button of elements.navButtons) {
      button.addEventListener("click", () => {
        state.view = button.dataset.view;
        render();
      });
    }
  }

  renderControls();
  renderAccountControls();
  bindEvents();
  render();
})();
