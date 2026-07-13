const state = {
  resume: null,
  match: null,
};

const elements = {
  form: document.querySelector("#analyzeForm"),
  apiBase: document.querySelector("#apiBase"),
  apiState: document.querySelector("#apiState"),
  file: document.querySelector("#resumeFile"),
  fileMeta: document.querySelector("#fileMeta"),
  job: document.querySelector("#jobDescription"),
  jobMeta: document.querySelector("#jobMeta"),
  parseButton: document.querySelector("#parseButton"),
  matchButton: document.querySelector("#matchButton"),
  status: document.querySelector("#status"),
  overallScore: document.querySelector("#overallScore"),
  scoreMeter: document.querySelector("#scoreMeter"),
  scoreVerdict: document.querySelector("#scoreVerdict"),
  skillScore: document.querySelector("#skillScore"),
  experienceScore: document.querySelector("#experienceScore"),
  educationScore: document.querySelector("#educationScore"),
  runMeta: document.querySelector("#runMeta"),
  profileList: document.querySelector("#profileList"),
  resumeSummary: document.querySelector("#resumeSummary"),
  matchedKeywords: document.querySelector("#matchedKeywords"),
  missingKeywords: document.querySelector("#missingKeywords"),
  recommendations: document.querySelector("#recommendations"),
  cleanedText: document.querySelector("#cleanedText"),
};

const storedApiBase = localStorage.getItem("resumeAnalyzerApiBase");
if (storedApiBase) {
  elements.apiBase.value = storedApiBase;
}

elements.apiBase.addEventListener("change", () => {
  localStorage.setItem("resumeAnalyzerApiBase", getApiBase());
  checkHealth();
});

elements.file.addEventListener("change", renderFileMeta);
elements.job.addEventListener("input", renderJobMeta);

elements.parseButton.addEventListener("click", async () => {
  await runParseOnly();
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runFullAnalysis();
});

renderFileMeta();
renderJobMeta();
checkHealth();

async function runParseOnly() {
  setBusy(true, "正在解析 PDF...");
  try {
    state.resume = await uploadResume();
    state.match = null;
    renderResume(state.resume);
    resetMatch();
    setStatus(`解析完成：${state.resume.page_count} 页，${state.resume.cached ? "命中缓存" : "新解析"}`);
  } catch (error) {
    setError(error.message);
  } finally {
    setBusy(false);
  }
}

async function runFullAnalysis() {
  setBusy(true, "正在解析并计算匹配度...");
  try {
    state.resume = await uploadResume();
    renderResume(state.resume);
    state.match = await matchResume(state.resume.resume_id, elements.job.value.trim());
    renderMatch(state.match);
    setStatus(`匹配完成：${state.match.cached ? "命中缓存" : "新计算"}，方法 ${state.match.scoring_method}`);
  } catch (error) {
    setError(error.message);
  } finally {
    setBusy(false);
  }
}

async function checkHealth() {
  elements.apiState.className = "connection-state";
  elements.apiState.textContent = "API 检测中...";
  try {
    const response = await fetch(`${getApiBase()}/health`);
    const payload = await parseResponse(response);
    elements.apiState.classList.add("ok");
    elements.apiState.textContent = `API 正常 · ${payload.cache} cache · LLM ${payload.llm_enabled ? "on" : "off"}`;
  } catch (error) {
    elements.apiState.classList.add("error");
    elements.apiState.textContent = "API 不可用，请检查地址或后端服务";
  }
}

async function uploadResume() {
  const file = elements.file.files[0];
  if (!file) {
    throw new Error("请选择 PDF 简历。");
  }
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getApiBase()}/api/v1/resumes`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

async function matchResume(resumeId, jobDescription) {
  if (!jobDescription || jobDescription.length < 10) {
    throw new Error("岗位需求至少需要 10 个字符。");
  }
  const response = await fetch(`${getApiBase()}/api/v1/resumes/${resumeId}/matches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_description: jobDescription }),
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || `HTTP ${response.status}`;
    throw new Error(Array.isArray(message) ? message.map((item) => item.msg).join("; ") : message);
  }
  return payload;
}

function renderResume(resume) {
  const info = resume.profile.basic_info || {};
  const intention = resume.profile.job_intention || {};
  const background = resume.profile.background || {};
  const skills = resume.profile.skills || [];
  const rows = [
    ["姓名", info.name],
    ["电话", info.phone],
    ["邮箱", info.email],
    ["地址", info.address],
    ["求职意向", intention.target_role],
    ["期望薪资", intention.expected_salary],
    ["工作年限", formatYears(background.years_of_experience)],
    ["学历", (background.education || []).join("；")],
    ["技能", skills.join("、")],
  ];

  elements.profileList.replaceChildren(...descriptionItems(rows));
  elements.resumeSummary.replaceChildren(
    ...descriptionItems([
      ["页数", `${resume.page_count}`],
      ["缓存", resume.cached ? "命中" : "未命中"],
      ["抽取方法", resume.profile.extraction_method || "--"],
      ["技能数", `${skills.length}`],
    ])
  );
  renderRunMeta(resume, state.match);
  elements.cleanedText.textContent = resume.cleaned_text || "--";
}

function renderMatch(match) {
  elements.overallScore.textContent = match.overall_score;
  elements.scoreMeter.style.width = `${match.overall_score}%`;
  elements.scoreVerdict.textContent = verdictForScore(match.overall_score);
  elements.skillScore.textContent = match.skill_score;
  elements.experienceScore.textContent = match.experience_score;
  elements.educationScore.textContent = match.education_score;
  renderTags(elements.matchedKeywords, match.matched_keywords || [], false);
  renderTags(elements.missingKeywords, match.missing_keywords || [], true);
  elements.recommendations.replaceChildren(
    ...(match.recommendations || []).map((item) => createTextElement("li", item))
  );
  renderRunMeta(state.resume, match);
}

function resetMatch() {
  elements.overallScore.textContent = "--";
  elements.scoreMeter.style.width = "0";
  elements.scoreVerdict.textContent = "等待岗位匹配";
  elements.skillScore.textContent = "--";
  elements.experienceScore.textContent = "--";
  elements.educationScore.textContent = "--";
  renderTags(elements.matchedKeywords, [], false);
  renderTags(elements.missingKeywords, [], true);
  elements.recommendations.replaceChildren(createTextElement("li", "输入岗位需求并点击匹配后显示建议。"));
}

function renderRunMeta(resume, match) {
  elements.runMeta.replaceChildren(
    ...descriptionItems([
      ["解析状态", resume ? `${resume.page_count} 页 · ${resume.cached ? "缓存" : "新解析"}` : "未开始"],
      ["评分方法", match?.scoring_method || "--"],
      ["Resume ID", resume?.resume_id || "--"],
    ])
  );
}

function renderTags(container, values, missing) {
  if (!values.length) {
    const empty = createTextElement("span", missing ? "无明显缺失" : "暂无匹配");
    empty.className = "tag";
    container.replaceChildren(empty);
    return;
  }
  container.replaceChildren(
    ...values.map((item) => {
      const tag = createTextElement("span", item);
      tag.className = `tag${missing ? " missing" : ""}`;
      return tag;
    })
  );
}

function renderFileMeta() {
  const file = elements.file.files[0];
  elements.fileMeta.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "尚未选择文件";
}

function renderJobMeta() {
  const length = elements.job.value.trim().length;
  elements.jobMeta.textContent = length ? `${length} 个字符` : "至少输入 10 个字符";
}

function descriptionItems(rows) {
  return rows.flatMap(([label, value]) => [createTextElement("dt", label), createTextElement("dd", value || "--")]);
}

function verdictForScore(score) {
  if (score >= 85) {
    return "优先进入人工复核";
  }
  if (score >= 70) {
    return "整体匹配，可继续确认缺失项";
  }
  if (score >= 55) {
    return "匹配一般，建议谨慎推进";
  }
  return "匹配偏弱，建议补充信息后复核";
}

function getApiBase() {
  return elements.apiBase.value.trim().replace(/\/$/, "");
}

function setBusy(isBusy, message) {
  elements.parseButton.disabled = isBusy;
  elements.matchButton.disabled = isBusy;
  if (message) {
    setStatus(message);
  }
}

function setStatus(message) {
  elements.status.classList.remove("error");
  elements.status.textContent = message;
}

function setError(message) {
  elements.status.classList.add("error");
  elements.status.textContent = message;
}

function formatYears(value) {
  if (value === null || value === undefined) {
    return null;
  }
  return `${Number(value).toLocaleString("zh-CN")} 年`;
}

function formatBytes(value) {
  if (value < 1024 * 1024) {
    return `${Math.max(1, Math.round(value / 1024))} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function createTextElement(tagName, text) {
  const element = document.createElement(tagName);
  element.textContent = text;
  return element;
}

