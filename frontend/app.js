const state = {
  resume: null,
  match: null,
};

const elements = {
  form: document.querySelector("#analyzeForm"),
  apiBase: document.querySelector("#apiBase"),
  apiState: document.querySelector("#apiState"),
  dropZone: document.querySelector("#dropZone"),
  file: document.querySelector("#resumeFile"),
  fileMeta: document.querySelector("#fileMeta"),
  job: document.querySelector("#jobDescription"),
  jobMeta: document.querySelector("#jobMeta"),
  sampleJobButton: document.querySelector("#sampleJobButton"),
  parseButton: document.querySelector("#parseButton"),
  matchButton: document.querySelector("#matchButton"),
  demoButton: document.querySelector("#demoButton"),
  status: document.querySelector("#status"),
  statusText: document.querySelector("#statusText"),
  statusSpinner: document.querySelector("#statusSpinner"),
  overallScore: document.querySelector("#overallScore"),
  scoreMeter: document.querySelector("#scoreMeter"),
  scoreVerdict: document.querySelector("#scoreVerdict"),
  skillScore: document.querySelector("#skillScore"),
  experienceScore: document.querySelector("#experienceScore"),
  educationScore: document.querySelector("#educationScore"),
  runMeta: document.querySelector("#runMeta"),
  profileList: document.querySelector("#profileList"),
  resumeSummary: document.querySelector("#resumeSummary"),
  projectsPanel: document.querySelector("#projectsPanel"),
  projectList: document.querySelector("#projectList"),
  jobKeywords: document.querySelector("#jobKeywords"),
  matchedKeywords: document.querySelector("#matchedKeywords"),
  missingKeywords: document.querySelector("#missingKeywords"),
  recommendations: document.querySelector("#recommendations"),
  cleanedText: document.querySelector("#cleanedText"),
  copyJsonButton: document.querySelector("#copyJsonButton"),
};

// Deployed backend on Aliyun Function Compute (custom.debian10 runtime).
const PRODUCTION_API_BASE = "https://resume-yzer-api-qfiqdkwrkd.cn-hangzhou.fcapp.run";

const SAMPLE_JOB = `Python 后端实习生
职责：负责服务端接口开发与维护，参与简历解析、岗位匹配等 AI 功能落地。
要求：
- 熟悉 Python，了解 FastAPI 或 Flask 等 Web 框架
- 熟悉 RESTful API 设计，了解 Redis 缓存
- 了解 Docker、Serverless（如阿里云函数计算 FC）优先
- 计算机相关专业本科及以上，1 年以上项目或实习经验优先`;

// Pick a sensible default so the page works out of the box:
// - a value the user previously saved always wins;
// - when served from a real host (e.g. GitHub Pages), point at the FC backend;
// - only fall back to localhost when developing locally.
const storedApiBase = localStorage.getItem("resumeAnalyzerApiBase");
if (storedApiBase) {
  elements.apiBase.value = storedApiBase;
} else if (location.hostname && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
  elements.apiBase.value = PRODUCTION_API_BASE;
}

elements.apiBase.addEventListener("change", () => {
  localStorage.setItem("resumeAnalyzerApiBase", getApiBase());
  checkHealth();
});

elements.file.addEventListener("change", renderFileMeta);
elements.job.addEventListener("input", renderJobMeta);

elements.sampleJobButton.addEventListener("click", () => {
  elements.job.value = SAMPLE_JOB;
  renderJobMeta();
});

elements.parseButton.addEventListener("click", async () => {
  await runParseOnly();
});

elements.demoButton.addEventListener("click", () => {
  loadDemo();
});

elements.copyJsonButton.addEventListener("click", copyResultJson);

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runFullAnalysis();
});

setupDragAndDrop();
renderFileMeta();
renderJobMeta();
checkHealth();

function setupDragAndDrop() {
  const zone = elements.dropZone;
  ["dragenter", "dragover"].forEach((type) => {
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((type) => {
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      if (type === "dragleave" && zone.contains(event.relatedTarget)) {
        return;
      }
      zone.classList.remove("dragover");
    });
  });
  zone.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      elements.file.files = event.dataTransfer.files;
      renderFileMeta();
    }
  });
}

async function runParseOnly() {
  setBusy(true, "正在解析 PDF（扫描件走 OCR，可能需要十几秒）...");
  try {
    state.resume = await analyze(null);
    state.match = null;
    renderResume(state.resume);
    resetMatch();
    setStatus(
      `解析完成：${state.resume.page_count} 页 · ${sourceLabel(state.resume.source)} · ${
        state.resume.cached ? "命中缓存" : "新解析"
      }`
    );
  } catch (error) {
    setError(error.message);
  } finally {
    setBusy(false);
  }
}

async function runFullAnalysis() {
  const jd = elements.job.value.trim();
  if (jd.length < 10) {
    setError("岗位需求至少需要 10 个字符。");
    return;
  }
  setBusy(true, "正在解析并计算匹配度（扫描件走 OCR，可能需要十几秒）...");
  try {
    const result = await analyze(jd);
    state.resume = result.resume;
    state.match = result.match;
    renderResume(state.resume);
    if (state.match) {
      renderMatch(state.match);
    }
    setStatus(
      `分析完成：${sourceLabel(state.resume.source)} · ${
        state.match?.cached ? "匹配命中缓存" : "新计算"
      } · 方法 ${state.match?.scoring_method || "--"}`
    );
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
    const ocr = payload.ocr_enabled ? " · OCR on" : "";
    elements.apiState.textContent = `API 正常 · ${payload.cache} cache · LLM ${
      payload.llm_enabled ? "on" : "off"
    }${ocr}`;
  } catch (error) {
    elements.apiState.classList.add("error");
    elements.apiState.textContent = "API 不可用，请检查地址或后端服务";
  }
}

// Stateless one-shot: parse (and optionally match) in a single request. Passing
// jobDescription=null runs parse-only. This does not rely on server-side session
// state, so it works reliably on Serverless where the next request may hit a
// different instance.
async function analyze(jobDescription) {
  const file = elements.file.files[0];
  if (!file) {
    throw new Error("请选择 PDF 简历。");
  }
  const formData = new FormData();
  formData.append("file", file);
  if (jobDescription) {
    formData.append("job_description", jobDescription);
  }

  const response = await fetch(`${getApiBase()}/api/v1/analyze`, {
    method: "POST",
    body: formData,
  });
  const payload = await parseResponse(response);
  // Endpoint returns {resume, match}. Parse-only callers just want the resume.
  return jobDescription ? payload : payload.resume;
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
      ["文本来源", sourceLabel(resume.source)],
      ["缓存", resume.cached ? "命中" : "未命中"],
      ["抽取方法", resume.profile.extraction_method || "--"],
      ["技能数", `${skills.length}`],
    ])
  );
  renderProjects(background.projects || []);
  renderRunMeta(resume, state.match);
  elements.cleanedText.textContent = resume.cleaned_text || "--";
  elements.copyJsonButton.hidden = false;
}

function renderProjects(projects) {
  if (!projects.length) {
    elements.projectsPanel.hidden = true;
    return;
  }
  elements.projectsPanel.hidden = false;
  elements.projectList.replaceChildren(
    ...projects.map((project) => {
      const item = document.createElement("div");
      item.className = "project-item";

      const head = document.createElement("div");
      head.className = "project-head";
      head.append(createTextElement("span", project.name || "未命名项目"));
      if (project.role) {
        const role = createTextElement("span", project.role);
        role.className = "project-role";
        head.append(role);
      }
      item.append(head);

      if (project.description) {
        const desc = createTextElement("p", project.description);
        desc.className = "project-desc";
        item.append(desc);
      }

      if ((project.technologies || []).length) {
        const tags = document.createElement("div");
        tags.className = "tags";
        tags.append(
          ...project.technologies.map((tech) => {
            const tag = createTextElement("span", tech);
            tag.className = "tag";
            return tag;
          })
        );
        item.append(tags);
      }
      return item;
    })
  );
}

function renderMatch(match) {
  elements.overallScore.textContent = match.overall_score;
  elements.scoreMeter.style.width = `${match.overall_score}%`;
  elements.scoreMeter.className = scoreClass(match.overall_score);
  elements.scoreVerdict.textContent = verdictForScore(match.overall_score);
  elements.skillScore.textContent = match.skill_score;
  elements.experienceScore.textContent = match.experience_score;
  elements.educationScore.textContent = match.education_score;
  renderTags(elements.jobKeywords, match.job_analysis?.required_skills || [], "muted");
  renderTags(elements.matchedKeywords, match.matched_keywords || [], "matched");
  renderTags(elements.missingKeywords, match.missing_keywords || [], "missing");
  elements.recommendations.replaceChildren(
    ...(match.recommendations || []).map((item) => createTextElement("li", item))
  );
  renderRunMeta(state.resume, match);
}

function loadDemo() {
  state.resume = demoResume;
  state.match = demoMatch;
  renderResume(state.resume);
  renderMatch(state.match);
  setStatus("已加载公开演示数据；真实解析请连接后端 API 后上传 PDF。");
}

function resetMatch() {
  elements.overallScore.textContent = "--";
  elements.scoreMeter.style.width = "0";
  elements.scoreMeter.className = "";
  elements.scoreVerdict.textContent = "等待岗位匹配";
  elements.skillScore.textContent = "--";
  elements.experienceScore.textContent = "--";
  elements.educationScore.textContent = "--";
  renderTags(elements.jobKeywords, [], "muted");
  renderTags(elements.matchedKeywords, [], "matched");
  renderTags(elements.missingKeywords, [], "missing");
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

function renderTags(container, values, variant) {
  if (!values.length) {
    const emptyText = variant === "missing" ? "无明显缺失" : variant === "muted" ? "暂无" : "暂无匹配";
    const empty = createTextElement("span", emptyText);
    empty.className = "tag";
    container.replaceChildren(empty);
    return;
  }
  container.replaceChildren(
    ...values.map((item) => {
      const tag = createTextElement("span", item);
      tag.className = `tag${variant === "missing" ? " missing" : variant === "muted" ? " muted" : ""}`;
      return tag;
    })
  );
}

function renderFileMeta() {
  const file = elements.file.files[0];
  elements.fileMeta.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "尚未选择文件";
  elements.dropZone.classList.toggle("has-file", Boolean(file));
}

function renderJobMeta() {
  const length = elements.job.value.trim().length;
  elements.jobMeta.textContent = length ? `${length} 个字符` : "至少输入 10 个字符（仅匹配时需要）";
}

async function copyResultJson() {
  const data = state.match ? { resume: state.resume, match: state.match } : { resume: state.resume };
  try {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    const original = elements.copyJsonButton.textContent;
    elements.copyJsonButton.textContent = "已复制";
    setTimeout(() => {
      elements.copyJsonButton.textContent = original;
    }, 1500);
  } catch (error) {
    setError("复制失败，浏览器可能不支持剪贴板权限。");
  }
}

function descriptionItems(rows) {
  return rows.flatMap(([label, value]) => [createTextElement("dt", label), createTextElement("dd", value || "--")]);
}

function sourceLabel(source) {
  if (source === "ocr") {
    return "OCR 识别";
  }
  if (source === "text") {
    return "文本层";
  }
  return source || "--";
}

function scoreClass(score) {
  if (score >= 70) {
    return "score-good";
  }
  if (score >= 55) {
    return "score-mid";
  }
  return "score-low";
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
  elements.demoButton.disabled = isBusy;
  elements.statusSpinner.hidden = !isBusy;
  if (message) {
    setStatus(message);
  }
}

function setStatus(message) {
  elements.status.classList.remove("error");
  elements.statusText.textContent = message;
}

function setError(message) {
  elements.status.classList.add("error");
  elements.statusText.textContent = message;
  elements.statusSpinner.hidden = true;
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

const demoResume = {
  resume_id: "demo-resume",
  file_name: "sample_resume.pdf",
  file_sha256: "demo",
  page_count: 1,
  cached: false,
  source: "text",
  cleaned_text:
    "Zhang San\nPhone: 13800001234\nEmail: zhangsan@example.com\nAddress: Beijing Haidian District\nTarget Role: Python Backend Intern\nEducation: Peking University, Bachelor of Computer Science\n2 years of backend development experience.\nSkills: Python, FastAPI, Redis, Docker, React, SQL, Git, pytest, Serverless, Aliyun FC",
  sections: [],
  profile: {
    basic_info: {
      name: "Zhang San",
      phone: "13800001234",
      email: "zhangsan@example.com",
      address: "Beijing Haidian District",
    },
    job_intention: {
      target_role: "Python Backend Intern",
      expected_salary: "150-200 RMB/day",
    },
    background: {
      years_of_experience: 2,
      education: ["Peking University, Bachelor of Computer Science"],
      projects: [
        {
          name: "AI Resume Analyzer",
          role: "Backend Developer",
          description: "Built PDF parsing, keyword extraction, Redis cache, and job matching APIs.",
          technologies: ["Python", "FastAPI", "Redis", "React"],
        },
      ],
    },
    skills: ["Aliyun FC", "Backend", "Docker", "FastAPI", "Python", "React", "Redis", "RESTful", "Serverless"],
    summary: "2 years of experience; skills: Python, FastAPI, Redis, React",
    extraction_method: "demo",
  },
};

const demoMatch = {
  resume_id: "demo-resume",
  job_analysis: {
    keywords: ["Python", "FastAPI", "Redis", "Docker", "React", "RESTful", "Serverless"],
    required_skills: ["Python", "FastAPI", "Redis", "Docker", "React", "RESTful", "Serverless"],
    seniority_hint: "junior",
    education_hint: "本科",
  },
  overall_score: 86,
  skill_score: 88,
  experience_score: 90,
  education_score: 80,
  matched_keywords: ["Python", "FastAPI", "Redis", "Docker", "React", "RESTful", "Serverless"],
  missing_keywords: ["函数计算"],
  recommendations: ["技能覆盖度高，建议面试重点追问 Serverless 部署、PDF 解析边界和缓存失效策略。"],
  scoring_method: "demo",
  cached: false,
};
