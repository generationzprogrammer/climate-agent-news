const state = {
  mode: "climate", language: "zh", datasets: {},
  dashboard: null, archive: null, analytics: null, filtered: [], visible: 18,
  mapPeriod: "today", mapTopology: null,
  assistant: { lastRecords: [], lastPlan: null },
  siteMetrics: null, subscription: null, team: null,
  companyData: null, companyFiltered: [], companyVisible: 12, companyMapPeriod: "today",
  reportData: null, reportFiltered: [], reportVisible: 12,
  spotlights: null, carbonTopic: "", singaporeAgency: "",
  topicDesks: null, transitionTracker: null, transitionCountry: "",
  carbonRegistry: null, carbonRegistryFiltered: [], carbonRegistryVisible: 24,
  taxonomy: { organization_groups: [], countries: [] },
};
const $ = id => document.getElementById(id);
const UI_TEXT = {
  zh: {
    navMap: "全球现场", navToday: "今日情报", navFocus: "专题", navChinaCarbon: "中国碳市场",
    navSingapore: "新加坡", navBth: "京津冀绿色转型", navRenewable: "新能源", navStorage: "储能技术", navAidc: "人工智能数据中心",
    navAnalytics: "语料分析", navAssistant: "情报问答", navDatabase: "文本数据库",
    chinaCarbonTitle: "中国碳市场", singaporeTitle: "新加坡气候政策与行动", all: "全部", source: "查看原文 ↗",
    archive: "站内新增", agencyAll: "全部机构", coverage: "官方机构 · 近一年", siteSubtitle: "国际气候情报与文本数据库",
    team: "团队信息", subscribe: "订阅", download: "下载今日简报", archiveChart: "累计气候文本档案", visitorChart: "累计访客/访问量",
    todayQueue: "今日队列", thisWeek: "本周", projectIntro: "项目介绍", projectIntroTitle: "项目介绍",
    navCompany: "企业情报", navEnergyReports: "能源报告与数据库", companyIntelligence: "企业情报",
    companyScope: "持续扩展的全球能源企业名录，以及从站内新闻中识别的重大项目、初创企业和企业合作。",
    energyReportsTitle: "能源报告与数据库", footerSubtitle: "国际气候与能源信息智能分析支持系统",
    carbonCompanyTitle: "全国重点排放单位名录", searchEntity: "检索单位", carbonCompanyPlaceholder: "单位名称或统一社会信用代码",
    entityType: "单位类别", allEntities: "全部单位", keyEmitter: "重点碳排放单位", generalReporting: "一般报告单位",
    province: "省份", allProvinces: "全部省份", industry: "行业", allIndustries: "全部行业", district: "所属区", allDistricts: "全部地区", results: "当前结果",
    showMoreEntities: "显示更多单位", officialRegister: "查看官方名录 ↗", nationalMarketSource: "查看全国碳市场官方数据 ↗",
    companyDatabaseTitle: "能源公司数据库", companyDatabaseNote: "按企业名称、国家和业务方向检索；企业动态均可返回原文。",
    searchCompany: "检索企业", companyPlaceholder: "企业名称、国家或业务，如：储能、氢能", companyType: "企业类型",
    allCompanies: "全部企业", energyMajors: "能源巨头与龙头企业", energyStartups: "能源初创企业", identifiedCompanies: "动态识别企业",
    country: "国家", allCountries: "全部国家", showMoreCompanies: "显示更多企业", companyMapTitle: "全球企业情报现场",
    companyMapNote: "红点表示企业新闻涉及地点；若原文未明确项目地点，则以企业总部定位并清楚标注。",
    searchResources: "检索资源", reportPlaceholder: "报告、数据库、机构或主题，如：电池、核聚变", resourceType: "资源类型",
    allTypes: "全部类型", energyReport: "能源报告", energyDatabase: "能源数据库", countryOrganization: "国家或组织",
    allCountryOrganizations: "全部国家或组织", internationalOrganization: "国际组织", allInternationalOrganizations: "全部国际组织",
    year: "年份", allYears: "全部年份", showMoreResources: "显示更多资源",
    cognitionTitle: "情报认知地图", knowledgeGraph: "国家—议题知识图谱", todayWordCloud: "今日情报关键词", transitionTracker: "能源转型进程信号追踪",
    dailyUpdate: "每日 06:30 自动更新", archivedTexts: "已归档文本", todaySignals: "今日重点情报", todayPlaces: "今日涉及地点", itemsUnit: "条", placesUnit: "个",
    monthlyFrequency: "月度文本频率", monthlyFrequencyNote: "按发布时间聚合；用于观察议题热度和采集覆盖的时间变化。",
    topicMix: "高频主题", topicMixNote: "按记录主题标签计数，一条文本可对应多个主题。", countryDistribution: "国家/地区分布",
    countryDistributionNote: "仅统计文本或地点字段明确出现的国家/地区。", regionalStructure: "洲别结构", regionalStructureNote: "按国家/地区标签映射到洲别；全球性文本保留未标注。",
    sourceMix: "主要来源", sourceMixNote: "用于识别语料来源集中度和后续补源方向。", countryTopic: "国家—主题热力矩阵",
    countryTopicNote: "显示主要国家/地区与高频主题的共现关系，便于后续分类和趋势建模。", evidenceSearch: "零费用站内证据检索",
    assistantIntroTitle: "从问题到证据，而不只是列标题", assistantIntroNote: "可要求比较国家、梳理时间线、提取政策含义，也可继续追问上一轮证据。若档案不足，系统会明确说明。",
    assistantName: "情报助手", assistantGreeting: "您好。我可以基于本站档案生成简报、国家比较、时间线和政策含义；回答均附原文证据。",
    askDatabase: "向情报库提问", chatPlaceholder: "例如：本周拉丁美洲有哪些重要动态？", send: "发送", search: "检索",
    archivePlaceholder: "搜索中文标题、原文、来源、议题或地域", topic: "议题", countryPlaceholder: "中国、CN或CHN", date: "日期",
    textRecord: "文本记录", sourceTopic: "来源 / 议题", figuresPlaces: "关键数字 / 地域", showMoreRecords: "显示更多记录",
  },
  en: {
    navMap: "Global desk", navToday: "Today", navFocus: "Focus", navChinaCarbon: "China carbon market",
    navSingapore: "Singapore", navAnalytics: "Corpus", navAssistant: "Q&A", navDatabase: "Text database",
    chinaCarbonTitle: "China carbon market", singaporeTitle: "Singapore climate policy and action", all: "All", source: "Open source ↗",
    navBth: "BTH green transition", navRenewable: "New energy", navStorage: "Energy storage", navAidc: "AI data centres",
    cognitionTitle: "Intelligence map", knowledgeGraph: "Country–topic knowledge graph", todayWordCloud: "Today's intelligence terms", transitionTracker: "Energy-transition signal tracker",
    archive: "New from archive", agencyAll: "All agencies", coverage: "Official institutions · past 12 months", siteSubtitle: "International climate intelligence and text database",
    team: "Team", subscribe: "Subscribe", download: "Download today's brief", archiveChart: "Cumulative climate text archive", visitorChart: "Cumulative visits / page views",
    todayQueue: "Today", thisWeek: "This week", projectIntro: "About", projectIntroTitle: "About the project",
    navCompany: "Companies", navEnergyReports: "Energy reports & data", companyIntelligence: "Company intelligence",
    companyScope: "A growing directory of global energy companies, projects, start-ups and corporate partnerships identified in the archive.",
    energyReportsTitle: "Energy reports and databases", footerSubtitle: "Intelligent analysis for international climate and energy information",
    carbonCompanyTitle: "National key-emitter register", searchEntity: "Search entities", carbonCompanyPlaceholder: "Entity name or unified social credit code",
    entityType: "Entity type", allEntities: "All entities", keyEmitter: "Key emitters", generalReporting: "General reporting entities",
    province: "Province", allProvinces: "All provinces", industry: "Industry", allIndustries: "All industries", district: "District", allDistricts: "All districts", results: "Results",
    showMoreEntities: "Show more entities", officialRegister: "Official register ↗", nationalMarketSource: "Official national ETS data ↗",
    companyDatabaseTitle: "Energy company database", companyDatabaseNote: "Search by company, country or business area; every intelligence item links to its source.",
    searchCompany: "Search companies", companyPlaceholder: "Company, country or business area", companyType: "Company type",
    allCompanies: "All companies", energyMajors: "Energy majors and leaders", energyStartups: "Energy start-ups", identifiedCompanies: "Companies identified in news",
    country: "Country", allCountries: "All countries", showMoreCompanies: "Show more companies", companyMapTitle: "Global company intelligence",
    companyMapNote: "Markers show locations cited in company news; headquarters are used only when a project location is not stated.",
    searchResources: "Search resources", reportPlaceholder: "Report, database, institution or topic", resourceType: "Resource type",
    allTypes: "All types", energyReport: "Energy report", energyDatabase: "Energy database", countryOrganization: "Country or organisation",
    allCountryOrganizations: "All countries and organisations", internationalOrganization: "International organisation", allInternationalOrganizations: "All international organisations",
    year: "Year", allYears: "All years", showMoreResources: "Show more resources",
    dailyUpdate: "Updated daily at 06:30 Beijing time", archivedTexts: "Archived texts", todaySignals: "Priority signals", todayPlaces: "Mapped locations", itemsUnit: "items", placesUnit: "places",
    monthlyFrequency: "Monthly text frequency", monthlyFrequencyNote: "Grouped by publication date to show changes in topic attention and collection coverage.",
    topicMix: "Leading topics", topicMixNote: "Counts archive tags; one text may carry several topics.", countryDistribution: "Country and region distribution",
    countryDistributionNote: "Counts only countries and regions explicitly identified in text or location fields.", regionalStructure: "Continental structure", regionalStructureNote: "Maps country tags to continents; global records remain unassigned.",
    sourceMix: "Leading sources", sourceMixNote: "Shows source concentration and where coverage may need expansion.", countryTopic: "Country–topic matrix",
    countryTopicNote: "Shows co-occurrence between leading countries or regions and frequent topics.", evidenceSearch: "On-site evidence search · no usage fee",
    assistantIntroTitle: "From questions to evidence", assistantIntroNote: "Compare countries, construct timelines and examine policy implications. The system states when evidence is insufficient.",
    assistantName: "Intelligence assistant", assistantGreeting: "I can search the archive and produce briefings, country comparisons, timelines and policy implications, with links to source evidence.",
    askDatabase: "Ask the intelligence archive", chatPlaceholder: "For example: what mattered in Latin America this week?", send: "Send", search: "Search",
    archivePlaceholder: "Search titles, source text, publishers, topics or places", topic: "Topic", countryPlaceholder: "China, CN or CHN", date: "Date",
    textRecord: "Text record", sourceTopic: "Source / topic", figuresPlaces: "Figures / places", showMoreRecords: "Show more records",
  },
};
const tr = key => UI_TEXT[state.language]?.[key] || UI_TEXT.zh[key] || key;
const field = (item, zhKey, enKey) => state.language === "en"
  ? (item?.[enKey] || item?.title_original || item?.[zhKey] || "")
  : (item?.[zhKey] || item?.[enKey] || "");
const esc = (value = "") => String(value).replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));
const SVG_NS = "http://www.w3.org/2000/svg";
const MAP_CENTER_LON = 55;

function safeUrl(value) {
  try {
    const url = new URL(value, location.href);
    if (url.protocol === "http:") url.protocol = "https:";
    return url.protocol === "https:" ? url.href : "#";
  } catch (_) {
    return "#";
  }
}

function substantiveSummary(value) {
  const text = String(value || "").trim();
  if (!text) return false;
  return !["这条情报聚焦", "需要重点关注其对政策执行、谈判表述或风险研判的影响",
    "来源标题显示", "适合作为当日气候情报线索"].some(marker => text.includes(marker));
}

function intelligenceAtoms(item, limit = 5) {
  const places = (item.places || []).map(place => place.name_zh);
  return [...new Set([item.theme_zh, ...(item.topics || []), ...places, ...(item.numbers || [])]
    .map(value => String(value || "").trim())
    .filter(value => value && !["气候动态", "全球气候", "综合"].includes(value)))]
    .slice(0, limit);
}

function summaryOrAtoms(item) {
  const summary = state.language === "en" ? item.summary_source : item.summary_zh;
  if (substantiveSummary(summary)) return `<p>${esc(summary)}</p>`;
  if (state.language === "en") return "";
  const atoms = intelligenceAtoms(item);
  return atoms.length
    ? `<p>${esc([item.title_zh || item.title_original, atoms.join("、")].filter(Boolean).join("；"))}。</p>`
    : `<p>${esc(item.title_zh || item.title_original || "该情报的中文概括待下一次自动编译补充。")}</p>`;
}

function formatDate(value, withTime = false) {
  if (!value) return "时间待核";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(state.language === "en" ? "en-GB" : "zh-CN", withTime
    ? { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }
    : { year: "numeric", month: "2-digit", day: "2-digit" });
}

function beijingDay(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date);
  const get = type => parts.find(part => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function toast(message) {
  const element = $("toast");
  if (!element) return;
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 3200);
}

function closeMobileMenu() {
  const menu = $("mobileMenu");
  const toggle = $("mobileMenuToggle");
  if (!menu || !toggle) return;
  menu.hidden = true;
  toggle.setAttribute("aria-expanded", "false");
  toggle.textContent = "菜单";
}

function setupMobileMenu() {
  const menu = $("mobileMenu");
  const toggle = $("mobileMenuToggle");
  if (!menu || !toggle) return;
  toggle.addEventListener("click", () => {
    const opening = menu.hidden;
    menu.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.textContent = opening ? "关闭" : "菜单";
  });
  menu.querySelectorAll("a").forEach(link => link.addEventListener("click", closeMobileMenu));
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeMobileMenu(); });
  window.addEventListener("resize", () => { if (window.innerWidth > 1100) closeMobileMenu(); });
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

const MODE_COPY = {
  climate: {
    button: "切换到能源技术",
    mapOverline: "GLOBAL CLIMATE SITUATION",
    mapTitle: "全球气候现场",
    heroOverline: "DAILY CLIMATE TEXT INTELLIGENCE",
    heroTitle: "每天读懂全球气候变化<br><span>重点情报与文本数据库</span>",
    heroLede: "从国际机构、政府与专业媒体中筛选值得关注的气候事件，提供中文标题、完整概要、议题、地域、关键数字及原文入口。",
    datasetName: "CLIMATETEXT-100000",
    datasetTitle: "每日气候文本档案",
    todayOverline: "DAILY SIGNALS",
    todayTitle: "今日重要气候情报",
    analyticsTitle: "语料库统计分析",
    assistantOverline: "GROUNDED CLIMATE Q&A",
    assistantTitle: "气候情报问答",
    databaseOverline: "TEXT DATABASE",
    databaseTitle: "气候新闻文本数据库",
    downloadName: "国际气候情报今日简报",
    quickPrompts: [
      ["今日简报", "请给出今日简报"],
      ["本周重点", "本周有哪些值得关注的气候情报？"],
      ["本周中美比较", "比较本周中国与美国的重点气候情报"],
      ["气候资金", "近期有哪些气候资金信息？"],
    ],
  },
  energy: {
    button: "切换到气候情报",
    mapOverline: "GLOBAL ENERGY TECHNOLOGY SITUATION",
    mapTitle: "全球能源技术现场",
    heroOverline: "DAILY ENERGY TECHNOLOGY INTELLIGENCE",
    heroTitle: "追踪能源转型与技术趋势<br><span>动态情报与文本数据库</span>",
    heroLede: "从现有归档中筛选能源转型、能源技术趋势、数字能源、新型电力系统、储能、风光氢网等相关信息，保留来源、时间、地域与原文入口。",
    datasetName: "ENERGYTECH-100000",
    datasetTitle: "能源技术文本档案",
    todayOverline: "ENERGY TECH SIGNALS",
    todayTitle: "今日能源技术动态",
    analyticsTitle: "能源技术语料分析",
    assistantOverline: "GROUNDED ENERGY TECH Q&A",
    assistantTitle: "能源技术情报问答",
    databaseOverline: "ENERGY TEXT DATABASE",
    databaseTitle: "能源技术文本数据库",
    downloadName: "能源技术趋势今日简报",
    quickPrompts: [
      ["今日能源动态", "请给出今日能源技术动态简报"],
      ["本周技术趋势", "本周有哪些值得关注的能源技术趋势？"],
      ["中美能源技术", "比较本周中国与美国的能源技术动态"],
      ["数能与电网", "近期有哪些数字能源、储能或电网信息？"],
    ],
  },
};

const MODE_COPY_EN = {
  climate: {
    button: "Switch to energy technology", mapOverline: "GLOBAL CLIMATE SITUATION", mapTitle: "Global climate desk",
    heroOverline: "DAILY CLIMATE TEXT INTELLIGENCE", heroTitle: "Understand global climate change every day<br><span>Priority intelligence and text database</span>",
    heroLede: "Selected developments from international organisations, governments and specialist media, with source text, topics, locations, figures and links.",
    datasetName: "CLIMATETEXT-100000", datasetTitle: "Daily climate text archive", todayOverline: "DAILY SIGNALS", todayTitle: "Today's priority climate intelligence",
    analyticsTitle: "Corpus analytics", assistantOverline: "GROUNDED CLIMATE Q&A", assistantTitle: "Climate intelligence Q&A",
    databaseOverline: "TEXT DATABASE", databaseTitle: "Climate news text database", downloadName: "Daily-climate-intelligence-brief",
    quickPrompts: [["Today's brief", "Please provide today's climate briefing"], ["This week", "What climate intelligence matters this week?"], ["China and US", "Compare China and US climate intelligence this week"], ["Climate finance", "What recent climate-finance developments are in the archive?"]],
  },
  energy: {
    button: "Switch to climate intelligence", mapOverline: "GLOBAL ENERGY TECHNOLOGY SITUATION", mapTitle: "Global energy technology desk",
    heroOverline: "DAILY ENERGY TECHNOLOGY INTELLIGENCE", heroTitle: "Track energy transition and technology<br><span>Dynamic intelligence and text database</span>",
    heroLede: "A source-linked view of energy transition, technology, digital energy, power systems, storage, wind, solar and hydrogen.",
    datasetName: "ENERGYTECH-100000", datasetTitle: "Energy technology text archive", todayOverline: "ENERGY TECH SIGNALS", todayTitle: "Today's energy technology intelligence",
    analyticsTitle: "Energy corpus analytics", assistantOverline: "GROUNDED ENERGY TECH Q&A", assistantTitle: "Energy technology Q&A",
    databaseOverline: "ENERGY TEXT DATABASE", databaseTitle: "Energy technology text database", downloadName: "Daily-energy-technology-brief",
    quickPrompts: [["Today's energy", "Please provide today's energy technology briefing"], ["Weekly trends", "What energy technology trends matter this week?"], ["China and US", "Compare China and US energy technology this week"], ["Digital grids", "What recent digital-energy, storage or grid developments are in the archive?"]],
  },
};

function modeCopy() {
  const table = state.language === "en" ? MODE_COPY_EN : MODE_COPY;
  return table[state.mode] || table.climate;
}

function applyModeCopy() {
  const copy = modeCopy();
  document.body.dataset.mode = state.mode;
  document.body.dataset.language = state.language;
  document.documentElement.lang = state.language === "en" ? "en" : "zh-CN";
  document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = tr(element.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.placeholder = tr(element.dataset.i18nPlaceholder); });
  const climateBrand = state.mode !== "energy";
  if ($("brandTitle")) $("brandTitle").textContent = climateBrand ? "格润气候治理" : "格润能源技术";
  if ($("brandDescriptor")) $("brandDescriptor").textContent = climateBrand ? "climate governance" : "energy technology";
  if ($("footerBrand")) $("footerBrand").textContent = climateBrand ? "格润气候治理" : "格润能源技术";
  const firstOptionLabels = {
    companyCountryFilter: "allCountries", energyReportCountry: "allCountryOrganizations", energyReportYear: "allYears",
    carbonProvinceFilter: "allProvinces", carbonIndustryFilter: "allIndustries",
  };
  Object.entries(firstOptionLabels).forEach(([id, key]) => { if ($(id)?.options?.[0]) $(id).options[0].textContent = tr(key); });
  [$("languageToggle"), $("mobileLanguageToggle")].filter(Boolean).forEach(button => {
    button.textContent = state.language === "en" ? "中文" : "EN";
  });
  [$("modeToggle"), $("mobileModeToggle")].filter(Boolean).forEach(button => { button.textContent = copy.button; });
  ["mapOverline", "mapTitle", "heroOverline", "heroLede", "datasetName", "datasetTitle",
    "todayOverline", "todayTitle", "analyticsTitle", "assistantOverline", "assistantTitle",
    "databaseOverline", "databaseTitle"].forEach(id => {
    const element = $(id);
    if (element) element.textContent = copy[id];
  });
  if ($("heroTitle")) $("heroTitle").innerHTML = copy.heroTitle;
  const energyMode = state.mode === "energy";
  document.querySelectorAll(".climate-only-nav, .climate-only-section").forEach(element => { element.hidden = energyMode; });
  document.querySelectorAll(".energy-only-nav, .energy-only-section").forEach(element => { element.hidden = !energyMode; });
  document.querySelectorAll(".energy-only-nav, .energy-only-section").forEach(element => { element.hidden = !energyMode; });
  if ($("companies")) $("companies").hidden = !energyMode;
  if ($("companyNav")) $("companyNav").hidden = !energyMode;
  if ($("energyReports")) $("energyReports").hidden = !energyMode;
  if ($("reportNav")) $("reportNav").hidden = !energyMode;
  if ($("mobileCompanyNav")) $("mobileCompanyNav").hidden = !energyMode;
  if ($("mobileReportNav")) $("mobileReportNav").hidden = !energyMode;
  document.querySelectorAll(".quick-prompts button").forEach((button, index) => {
    const prompt = copy.quickPrompts?.[index];
    if (!prompt) return;
    button.textContent = prompt[0];
    button.dataset.prompt = prompt[1];
  });
}

function activateMode(mode) {
  const nextMode = mode === "energy" && state.datasets.energy ? "energy" : "climate";
  const dataset = state.datasets[nextMode];
  state.mode = nextMode;
  state.dashboard = dataset.dashboard;
  state.archive = dataset.archive;
  state.analytics = dataset.analytics;
  state.filtered = [];
  state.visible = 18;
  state.assistant = { lastRecords: [], lastPlan: null };
  localStorage.setItem("climateTextMode", nextMode);
  applyModeCopy();
  setupTaxonomyFilters();
  if (state.mode === "energy" && state.companyData) renderCompanyIntelligence();
  if (state.mode === "energy" && state.reportData) renderEnergyReports();
  if (state.spotlights) renderSpotlights();
  if (state.carbonRegistry) renderCarbonRegistry();
  renderTopicDesks();
  renderCognition();
  renderTransitionTracker();
  renderProjectIntro();
  renderMeta();
  renderToday();
  if ($("archiveSearch")) $("archiveSearch").value = "";
  populateTopicFilter();
  applyFilters();
  renderAnalytics();
  updateMapPeriodCounts();
  switchMapPeriod("today").catch(error => {
    console.error("Mode map rendering failed", error);
    toast("地图刷新失败，请稍后重试。");
  });
}

function renderMeta() {
  const dashboard = state.dashboard;
  const archive = state.archive;
  const events = dashboard.map_events_today || dashboard.map_events || [];
  const uniquePlaces = new Set(events.map(item => item.place).filter(Boolean));
  $("archiveTotal").textContent = archive.total ?? 0;
  $("todayTotal").textContent = (dashboard.intelligence || []).length;
  $("mapPlaceTotal").textContent = uniquePlaces.size;
  $("datasetVersion").textContent = formatDate(archive.updated_at, true);
  $("generatedAt").textContent = `${state.language === "en" ? "Generated: " : "最近生成："}${formatDate(dashboard.meta?.generated_at, true)}`;
  const briefLink = $("briefDownload");
  if (briefLink) briefLink.download = `${modeCopy().downloadName}-${dashboard.meta?.date || "latest"}.pdf`;
}

function renderMiniLineChart(id, rows, label) {
  const element = $(id);
  if (!element) return;
  if (!rows?.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无曲线数据</b></div>';
    return;
  }
  const width = 620, height = 168, left = 58, right = 18, top = 14, bottom = 36;
  const values = rows.map(row => Number(row.value || 0));
  const minValue = Math.min(...values);
  const rawMax = Math.max(...values);
  const rawRange = Math.max(1, rawMax - minValue);
  let tickStep = Math.max(1, Math.ceil(rawRange / 3));
  let yStart = Math.floor(minValue / tickStep) * tickStep;
  while (yStart + tickStep * 3 < rawMax) tickStep += 1;
  const yTicks = Array.from({ length: 4 }, (_, index) => yStart + tickStep * index);
  const maxValue = yTicks.at(-1);
  const span = Math.max(1, rows.length - 1);
  const px = index => left + index / span * (width - left - right);
  const py = value => top + (1 - (value - yStart) / Math.max(1, maxValue - yStart)) * (height - top - bottom);
  const points = rows.map((row, index) => [px(index), py(Number(row.value || 0))]);
  const path = points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
  const area = `${path} L${points.at(-1)[0].toFixed(1)},${height - bottom} L${points[0][0].toFixed(1)},${height - bottom} Z`;
  const tickIndexes = [...new Set(Array.from({ length: 5 }, (_, index) => Math.round(span * index / 4)))];
  const dateLabel = value => {
    const parts = String(value || "").split("-");
    if (parts.length !== 3) return value;
    if (state.language === "en") return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    return `${Number(parts[1])}月${Number(parts[2])}日`;
  };
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}">
    ${yTicks.map(value => {
      const y = py(value);
      return `<line class="chart-gridline" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"></line><text class="chart-muted mini-axis-label" x="${left - 8}" y="${y + 4}" text-anchor="end">${Math.round(value)}</text>`;
    }).join("")}
    <line class="chart-axis" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
    <path class="chart-area" d="${area}"></path>
    <path class="chart-line" d="${path}"></path>
    ${tickIndexes.map(index => `<line class="chart-axis-tick" x1="${px(index)}" y1="${height - bottom}" x2="${px(index)}" y2="${height - bottom + 4}"></line><circle class="chart-dot chart-hover-dot" cx="${points[index][0]}" cy="${points[index][1]}" r="4"><title>${esc(rows[index].date)}：${Math.round(values[index])}</title></circle><text class="chart-muted mini-axis-label" x="${px(index)}" y="${height - 10}" text-anchor="middle">${esc(dateLabel(rows[index].date))}</text>`).join("")}
  </svg>`;
}

function organizationOptions() {
  return (state.taxonomy?.organization_groups || []).map(group => ({
    label: state.language === "en" ? (group.label_en || group.label_zh) : group.label_zh,
    items: group.organizations || [],
  }));
}

function fillOrganizationSelect(element, allLabel = "全部国际组织") {
  if (!element) return;
  element.innerHTML = `<option value="">${esc(allLabel)}</option>` + organizationOptions().map(group =>
    `<optgroup label="${esc(group.label)}">${group.items.map(item =>
      `<option value="${esc(item.code)}">${esc(state.language === "en" ? (item.name_en || item.name_zh) : item.name_zh)} (${esc(item.code)})</option>`
    ).join("")}</optgroup>`
  ).join("");
}

function setupTaxonomyFilters() {
  [$("todayOrganizationFilter"), $("organizationFilter"), $("energyReportOrganization")]
    .forEach(element => fillOrganizationSelect(element));
  const datalist = $("countryCodeList");
  if (datalist) datalist.innerHTML = (state.taxonomy?.countries || [])
    .slice().sort((a, b) => String(a.name_zh).localeCompare(String(b.name_zh), "zh-CN"))
    .map(country => `<option value="${esc(country.name_zh)}">${esc(country.alpha2)} · ${esc(country.alpha3)}</option>`)
    .join("");
}

function spotlightCard(item, label) {
  const title = field(item, "title_zh", "title_en");
  const summary = field(item, "summary_zh", "summary_en");
  const source = field(item, "source_zh", "source_en") || item.source_name || "";
  return `<article class="spotlight-card">
    <div class="spotlight-card-meta"><span>${esc(label)}</span><span>${esc(formatDate(item.published_at))}</span></div>
    <h3>${esc(title)}</h3>${summary ? `<p>${esc(summary)}</p>` : ""}
    <div class="spotlight-card-foot"><span>${esc(source)}</span><a href="${esc(safeUrl(item.url || item.canonical_url))}" target="_blank" rel="noopener noreferrer">${esc(tr("source"))}</a></div>
  </article>`;
}

function renderSpotlights() {
  const data = state.spotlights;
  if (!data || !$('carbonSpotlightList')) return;
  const carbon = data.china_carbon_market || { topics: [], records: [] };
  if ($('carbonAgencies')) $('carbonAgencies').innerHTML = (carbon.agencies || []).map(agency => `<a class="agency-card" href="${esc(safeUrl(agency.url))}" target="_blank" rel="noopener noreferrer"><b>${esc(field(agency, "name_zh", "name_en"))}</b><span>${esc(field(agency, "role_zh", "role_en"))}</span><i>${esc(agency.id)} ↗</i></a>`).join("");
  const topics = [{ id: "", label_zh: "全部", label_en: "All" }, ...(carbon.topics || [])];
  $('carbonTopicTabs').innerHTML = topics.map(topic => `<button class="${state.carbonTopic === topic.id ? "active" : ""}" type="button" data-carbon-topic="${esc(topic.id)}">${esc(field(topic, "label_zh", "label_en"))}</button>`).join("");
  const englishReady = item => /[A-Za-z]{4}/.test(String(item.title_en || "")) && /[A-Za-z]{8}/.test(String(item.summary_en || ""));
  const carbonRows = (carbon.records || [])
    .filter(item => !state.carbonTopic || item.topic === state.carbonTopic)
    .filter(item => state.language !== "en" || englishReady(item));
  $('carbonSpotlightList').innerHTML = carbonRows.length ? carbonRows.map(item => {
    const topic = (carbon.topics || []).find(value => value.id === item.topic);
    return spotlightCard(item, item.dynamic ? tr("archive") : field(topic || {}, "label_zh", "label_en") || tr("archive"));
  }).join("") : '<div class="empty compact"><b>No matching records</b></div>';
  document.querySelectorAll('[data-carbon-topic]').forEach(button => button.addEventListener('click', () => {
    state.carbonTopic = button.dataset.carbonTopic || ""; renderSpotlights();
  }));

  const singapore = data.singapore || { agencies: [], records: [] };
  $('singaporeCoverage').textContent = tr("coverage");
  $('singaporeAgencies').innerHTML = (singapore.agencies || []).map(agency => `<a class="agency-card" href="${esc(safeUrl(agency.url))}" target="_blank" rel="noopener noreferrer"><b>${esc(field(agency, "name_zh", "name_en"))}</b><span>${esc(field(agency, "parent_zh", "parent_en"))}</span><i>${esc(agency.id)} ↗</i></a>`).join("");
  const agencies = [{ id: "", name_zh: "全部机构", name_en: "All agencies" }, ...(singapore.agencies || [])];
  $('singaporeAgencyTabs').innerHTML = agencies.map(agency => `<button class="${state.singaporeAgency === agency.id ? "active" : ""}" type="button" data-singapore-agency="${esc(agency.id)}">${esc(field(agency, "name_zh", "name_en"))}</button>`).join("");
  const singaporeRows = (singapore.records || [])
    .filter(item => !state.singaporeAgency || item.agency === state.singaporeAgency)
    .filter(item => state.language !== "en" || englishReady(item));
  $('singaporeSpotlightList').innerHTML = singaporeRows.length ? singaporeRows.map(item => {
    const agency = (singapore.agencies || []).find(value => value.id === item.agency);
    return spotlightCard(item, item.dynamic ? tr("archive") : (agency?.id || item.agency));
  }).join("") : '<div class="empty compact"><b>No matching records</b></div>';
  document.querySelectorAll('[data-singapore-agency]').forEach(button => button.addEventListener('click', () => {
    state.singaporeAgency = button.dataset.singaporeAgency || ""; renderSpotlights();
  }));
}

function renderTopicDesks() {
  const root = $("topicDeskList");
  if (!root) return;
  const desks = (state.topicDesks?.desks || []).filter(desk => desk.mode === state.mode);
  root.innerHTML = desks.map(desk => `<section class="section spotlight-section topic-desk" id="${esc(desk.id)}">
    <div class="section-heading"><div><p class="overline">FOCUS DESK</p><h2>${esc(field(desk, "title_zh", "title_en"))}</h2></div></div>
    <div class="agency-grid">${(desk.agencies || []).map(agency => `<a class="agency-card" href="${esc(safeUrl(agency.url))}" target="_blank" rel="noopener noreferrer"><b>${esc(field(agency, "name_zh", "name_en"))}</b><i>↗</i></a>`).join("")}</div>
    <div class="spotlight-grid">${(desk.records || []).slice(0, 12).map(item => spotlightCard(item, item.dynamic ? tr("archive") : "FOCUS")).join("") || '<div class="empty compact"><b>暂无匹配记录</b></div>'}</div>
  </section>`).join("");
}

function renderCognition() {
  renderKnowledgeGraph();
  const cloud = $("todayWordCloud");
  if (!cloud) return;
  const counts = new Map();
  (state.dashboard?.intelligence || []).forEach(item => {
    const values = [...(item.topics || []), ...(item.keywords || []), item.topic].filter(Boolean);
    values.forEach(value => counts.set(String(value), (counts.get(String(value)) || 0) + 1));
  });
  const rows = [...counts].sort((a, b) => b[1] - a[1]).slice(0, 24);
  const max = Math.max(1, ...rows.map(row => row[1]));
  cloud.innerHTML = rows.length ? rows.map(([name, count], index) => `<span style="--term-size:${(16 + count / max * 22).toFixed(1)}px;--term-tone:${index % 3}" title="${esc(name)}：${count}">${esc(name)}</span>`).join("") : '<div class="empty compact"><b>暂无关键词</b></div>';
}

function renderKnowledgeGraph() {
  const element = $("knowledgeGraph");
  const matrix = state.analytics?.country_topic_matrix || {};
  const countries = (matrix.countries || []).slice(0, 6);
  const topics = (matrix.topics || []).slice(0, 6);
  if (!countries.length || !topics.length) {
    if (element) element.innerHTML = '<div class="empty compact"><b>暂无共现数据</b></div>';
    return;
  }
  const cells = matrix.cells || [];
  const max = Math.max(1, ...cells.map(cell => Number(cell.count || 0)));
  const countryPos = new Map(countries.map((name, i) => [name, [110, 45 + i * 45]]));
  const topicPos = new Map(topics.map((name, i) => [name, [490, 45 + i * 45]]));
  const edges = cells.filter(cell => countryPos.has(cell.country) && topicPos.has(cell.topic) && cell.count).map(cell => {
    const [x1, y1] = countryPos.get(cell.country), [x2, y2] = topicPos.get(cell.topic);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="stroke-opacity:${(.12 + .58 * cell.count / max).toFixed(2)}"><title>${esc(cell.country)} × ${esc(cell.topic)}：${cell.count}</title></line>`;
  }).join("");
  element.innerHTML = `<svg class="knowledge-svg" viewBox="0 0 600 320" role="img" aria-label="国家与议题共现网络">${edges}
    ${countries.map(name => { const [x,y]=countryPos.get(name); return `<g><circle cx="${x}" cy="${y}" r="7"></circle><text x="${x+14}" y="${y+4}">${esc(name)}</text></g>`; }).join("")}
    ${topics.map(name => { const [x,y]=topicPos.get(name); return `<g class="topic-node"><circle cx="${x}" cy="${y}" r="7"></circle><text x="${x+14}" y="${y+4}">${esc(name)}</text></g>`; }).join("")}</svg>`;
}

function renderTransitionTracker() {
  const section = $("transitionTracker");
  if (!section || state.mode !== "energy") return;
  const data = state.transitionTracker;
  const countries = data?.countries || [];
  if (!countries.length) return;
  if (!state.transitionCountry || !countries.some(item => item.alpha2 === state.transitionCountry)) state.transitionCountry = countries[0].alpha2;
  const englishNames = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames(["en"], { type: "region" }) : null;
  const countryName = item => state.language === "en" ? (englishNames?.of(item.alpha2) || item.alpha2) : item.name_zh;
  $("transitionCountryList").innerHTML = countries.map(item => `<button type="button" class="${item.alpha2 === state.transitionCountry ? "active" : ""}" data-transition-country="${esc(item.alpha2)}"><b>${esc(countryName(item))}</b><span>${esc(state.language === "en" ? item.signal_en : item.signal)}</span><i>${item.evidence_count}</i></button>`).join("");
  const country = countries.find(item => item.alpha2 === state.transitionCountry);
  $("transitionCountryTitle").textContent = countryName(country);
  const dimensions = data.dimensions || [], centre = 160, radius = 105, n = dimensions.length;
  const polar = (index, value) => { const angle = -Math.PI / 2 + index * Math.PI * 2 / n; return [centre + Math.cos(angle) * radius * value, centre + Math.sin(angle) * radius * value]; };
  const rings = [0.25,0.5,0.75,1].map(level => `<polygon points="${dimensions.map((_,i)=>polar(i,level).join(',')).join(' ')}"></polygon>`).join("");
  const points = dimensions.map((dimension, index) => polar(index, Number(country.scores?.[dimension.id] || 0) / 100));
  $("transitionRadar").innerHTML = `<svg class="radar-svg" viewBox="0 0 420 330" role="img" aria-label="${esc(countryName(country))}">${rings}${dimensions.map((dimension,i)=>{const [x,y]=polar(i,1);const label=state.language === "en" ? dimension.label_en : dimension.label_zh;return `<line x1="${centre}" y1="${centre}" x2="${x}" y2="${y}"></line><text x="${x}" y="${y}" text-anchor="middle">${esc(label)}</text>`;}).join('')}<polygon class="radar-value" points="${points.map(p=>p.join(',')).join(' ')}"></polygon>${points.map((p,i)=>{const label=state.language === "en" ? dimensions[i].label_en : dimensions[i].label_zh;return `<circle class="radar-point" cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(label)}：${country.scores[dimensions[i].id]}</title></circle>`;}).join('')}</svg>`;
  document.querySelectorAll("[data-transition-country]").forEach(button => button.addEventListener("click", () => { state.transitionCountry = button.dataset.transitionCountry; renderTransitionTracker(); }));
}

function setupCarbonRegistry() {
  const data = state.carbonRegistry;
  if (!data || !$("carbonEntityList")) return;
  const entities = data.entities || [];
  const provinces = [...new Set(entities.map(item => item.province).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  const industries = [...new Set(entities.map(item => item.industry).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  $("carbonProvinceFilter").innerHTML = `<option value="">${esc(tr("allProvinces"))}</option>${provinces.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}`;
  $("carbonIndustryFilter").innerHTML = `<option value="">${esc(tr("allIndustries"))}</option>${industries.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}`;
  ["carbonEntitySearch", "carbonProvinceFilter", "carbonIndustryFilter"].forEach(id => {
    const element = $(id);
    if (!element || element.dataset.bound) return;
    element.dataset.bound = "true";
    element.addEventListener(id === "carbonEntitySearch" ? "input" : "change", () => {
      state.carbonRegistryVisible = 24;
      applyCarbonRegistryFilters();
    });
  });
  if ($("carbonEntityLoadMore") && !$("carbonEntityLoadMore").dataset.bound) {
    $("carbonEntityLoadMore").dataset.bound = "true";
    $("carbonEntityLoadMore").addEventListener("click", () => {
      state.carbonRegistryVisible += 24;
      renderCarbonRegistry();
    });
  }
  applyCarbonRegistryFilters();
}

function applyCarbonRegistryFilters() {
  const query = $("carbonEntitySearch")?.value.trim().toLowerCase() || "";
  const province = $("carbonProvinceFilter")?.value || "";
  const industry = $("carbonIndustryFilter")?.value || "";
  state.carbonRegistryFiltered = (state.carbonRegistry?.entities || []).filter(item => {
    const haystack = `${item.name || ""} ${item.uscc || ""}`.toLowerCase();
    return (!query || haystack.includes(query)) && (!province || item.province === province) && (!industry || item.industry === industry);
  });
  renderCarbonRegistry();
}

function renderCarbonRegistry() {
  if (!state.carbonRegistry || !$("carbonEntityList")) return;
  const metadata = state.carbonRegistry.metadata || {};
  const entities = state.carbonRegistry.entities || [];
  const kpis = state.language === "en" ? [
    ["Searchable entities", entities.length], ["Provinces", metadata.province_count || 0],
    ["Industries", (metadata.industries || []).length], ["Official 2025 total", metadata.official_2025_total || "—"],
  ] : [
    ["可检索单位", entities.length], ["覆盖省份", metadata.province_count || 0],
    ["行业", (metadata.industries || []).length], ["2025年官方总量", metadata.official_2025_total || "—"],
  ];
  $("carbonCompanyKpis").innerHTML = kpis.map(([label, value]) => `<article><span>${esc(label)}</span><b>${Number(value).toLocaleString(state.language === "en" ? "en-GB" : "zh-CN")}</b></article>`).join("");
  if ($("carbonRegistrySource")) $("carbonRegistrySource").href = safeUrl(metadata.source_url);
  $("carbonEntityResultCount").textContent = state.carbonRegistryFiltered.length.toLocaleString(state.language === "en" ? "en-GB" : "zh-CN");
  const shown = state.carbonRegistryFiltered.slice(0, state.carbonRegistryVisible);
  $("carbonEntityList").innerHTML = shown.length ? shown.map(item => `<article class="carbon-register-card">
    <div><span>${esc(item.province)}</span><i>${esc(item.industry)}</i><i>${esc(item.registry_year)}</i></div>
    <h4>${esc(item.name)}</h4>
    <code>${esc(item.uscc)}</code>
  </article>`).join("") : `<div class="empty compact"><b>${state.language === "en" ? "No matching entities" : "没有匹配单位"}</b></div>`;
  $("carbonEntityLoadMore").hidden = state.carbonRegistryVisible >= state.carbonRegistryFiltered.length;
}

const PROJECT_INTRO = {
  zh: {
    paragraphs: [
      "在国家“双碳”战略与数字化绿色化协同转型背景下，清华大学气候变化与可持续发展研究院依托国际谈判与全球治理的真实场景需求，启动格润数据平台建设，服务政府、企业和机构投资者在绿色低碳转型中的数据获取与决策。",
      "2023年12月，《联合国气候变化框架公约》第二十八次缔约方大会期间，格润数据平台在迪拜中国角“数字经济与低碳发展”边会上正式发布。2025年11月，格润气候治理智能平台（GREEN 1.0版）在巴西贝伦第三十次缔约方大会中国角“数字化日”正式发布。",
      "平台以数字技术促进气候信息互联互通、数据开放共享与智能辅助决策，持续探索气候治理智库研究的新范式。",
    ],
    quotes: [
      ["深化人工智能等数字技术应用，构建美丽中国数字化治理体系，建设绿色智慧的数字生态文明。", "习近平总书记关于数字技术赋能生态文明建设的重要论述"],
      ["全球气候治理正进入坚定落实《巴黎协定》的新阶段，在可再生能源技术、政策解决方案、人才培养、公众动员等方面亟待创新解决方案。", "解振华，中国气候变化事务特使"],
      ["破题的关键在于技术创新，大数据和人工智能的结合将成为下一步绿色转型的核心技术驱动力。", "贺克斌，中国工程院院士、清华大学碳中和研究院院长"],
      ["清华大学长期致力于气候变化领域的战略研究与政策支持，希望格润平台为谈判者、决策者和智库研究人员提升信息获取与分析能力。", "李政，清华大学气候变化与可持续发展研究院院长"],
      ["信息不对称和碎片化，是制约国际气候谈判与合作效率的重要瓶颈之一。我们将持续以数字技术为桥梁，探索气候治理智库研究的新范式。", "宋伟泽，清华大学低碳能源实验室数据平台研究主任、GREEN项目负责人"],
    ],
  },
  en: {
    paragraphs: [
      "Against China's dual-carbon goals and the convergence of digital and green transformation, the Institute of Climate Change and Sustainable Development at Tsinghua University initiated the GREEN Data Platform to support governments, companies and institutional investors with decision-ready climate and energy information.",
      "The GREEN Data Platform was launched at the China Pavilion during COP28 in Dubai in December 2023. GREEN 1.0 was subsequently launched during Digitalisation Day at the China Pavilion of COP30 in Belém in November 2025.",
      "The platform uses digital technology to connect climate information, support open data and strengthen evidence-informed decisions, while exploring new methods for climate-governance research.",
    ],
    quotes: [
      ["Deepen the application of artificial intelligence and other digital technologies, and build a green, intelligent digital ecological civilisation.", "Xi Jinping, on digital technology and ecological civilisation"],
      ["Global climate governance is entering a new stage of firm implementation of the Paris Agreement and urgently needs innovative solutions.", "Xie Zhenhua, China's Special Envoy for Climate Change"],
      ["The key lies in technological innovation; the combination of big data and AI will be a core driver of green transformation.", "He Kebin, Member of the Chinese Academy of Engineering"],
      ["We hope GREEN can strengthen access to and analysis of information for negotiators, decision-makers and think tanks.", "Li Zheng, President of ICCSD, Tsinghua University"],
      ["Information asymmetry and fragmentation constrain international climate negotiations and cooperation. We will keep using digital technology to explore new research methods for climate governance.", "Song Weize, GREEN Project Lead"],
    ],
  },
};

function renderProjectIntro() {
  const copy = PROJECT_INTRO[state.language] || PROJECT_INTRO.zh;
  if (!$("projectIntroContent")) return;
  $("projectIntroContent").innerHTML = `<div class="project-intro-text">${copy.paragraphs.map(value => `<p>${esc(value)}</p>`).join("")}</div><div class="project-quotes">${copy.quotes.map(([quote, source]) => `<blockquote><p>${esc(quote)}</p><cite>${esc(source)}</cite></blockquote>`).join("")}</div>`;
}

function setupProjectIntro() {
  const modal = $("projectIntroModal");
  document.querySelectorAll("#projectIntroOpen, [data-open-project]").forEach(button => button.addEventListener("click", () => { closeMobileMenu(); renderProjectIntro(); openDialog(modal); }));
  $("projectIntroClose")?.addEventListener("click", () => closeDialog(modal));
  modal?.addEventListener("click", event => { if (event.target === modal) closeDialog(modal); });
}

function organizationCodes(record) {
  const tags = (record?.organization_tags || []).map(tag => typeof tag === "string" ? tag : tag.code).filter(Boolean);
  const text = [record?.title_original, record?.title_zh, record?.summary_source, record?.summary_zh].filter(Boolean).join(" ");
  if (/\b(?:belt and road initiative|BRI)\b|一带一路|丝绸之路经济带/i.test(text) && !tags.includes("BRI")) tags.push("BRI");
  return tags;
}

function matchesCountry(record, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [
    ...(record.country_codes || []).flatMap(country => [country.name_zh, country.alpha2, country.alpha3]),
    ...(record.places || []).map(place => place.name_zh),
  ].some(value => String(value || "").toLowerCase().includes(needle));
}

function renderSiteMetrics() {
  const metrics = state.siteMetrics || {};
  renderMiniLineChart("archiveGrowthChart", metrics.archive_cumulative || [], "累计气候文本档案曲线");
  renderMiniLineChart("visitorGrowthChart", metrics.visitor_cumulative || [], "累计访客访问量曲线");
}

function findArchiveRecord(item) {
  return state.archive.records.find(record =>
    record.article_id === item.article_id || record.canonical_url === item.canonical_url
  ) || item;
}

function renderToday() {
  const organization = $("todayOrganizationFilter")?.value || "";
  const items = (state.dashboard.intelligence || [])
    .filter(item => item.title_zh)
    .map(item => ({ item, record: findArchiveRecord(item) }))
    .filter(({ record }) => !organization || organizationCodes(record).includes(organization));
  $("todayGrid").innerHTML = items.length ? items.slice(0, 10).map(({ item, record }, index) => {
    const classification = [...organizationCodes(record), ...(record.event_tags || [])].slice(0, 3);
    return `<article class="signal-card">
      <div class="signal-index">${String(index + 1).padStart(2, "0")}</div>
      <div class="signal-content">
        <div class="signal-meta"><span class="topic">${esc(state.language === "en" ? (state.mode === "energy" ? "Energy technology" : "Climate") : (item.theme_zh || "气候动态"))}</span>${classification.map(tag => `<span>${esc(tag)}</span>`).join("")}</div>
        <h3>${esc(field(item, "title_zh", "title_original"))}</h3>
        ${summaryOrAtoms(item)}
        <div class="signal-foot">
          <span>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</span>
          <a href="${esc(safeUrl(record.canonical_url || item.url))}" target="_blank" rel="noopener noreferrer">${esc(tr("source"))}</a>
        </div>
      </div>
    </article>`;
  }).join("") : `<div class="empty"><b>${state.language === "en" ? "No new priority intelligence today" : "今日暂无新增重点情报"}</b><p>${state.language === "en" ? "The historical archive remains available and will update after the next valid collection run." : "网站仍保留历史文本数据库，待下一次有效数据更新后自动补充。"}</p></div>`;
}

function setupFilters() {
  populateTopicFilter();
  ["archiveSearch", "topicFilter", "organizationFilter", "countryFilter"].forEach(id => $(id)?.addEventListener(["archiveSearch", "countryFilter"].includes(id) ? "input" : "change", () => {
    state.visible = 18;
    applyFilters();
  }));
  $("todayOrganizationFilter")?.addEventListener("change", renderToday);
  $("loadMore").addEventListener("click", () => {
    state.visible += 18;
    renderArchiveRows();
  });
}

function populateTopicFilter() {
  const topics = [...new Set(state.archive.records.flatMap(record => record.topics || []))]
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  $("topicFilter").innerHTML = `<option value="">${state.language === "en" ? "All topics" : "全部议题"}</option>`
    + topics.map(topic => `<option value="${esc(topic)}">${esc(topic)}</option>`).join("");
}

function applyFilters() {
  const query = $("archiveSearch").value.trim().toLowerCase();
  const topic = $("topicFilter").value;
  const organization = $("organizationFilter")?.value || "";
  const country = $("countryFilter")?.value || "";
  state.filtered = state.archive.records.filter(record => {
    const haystack = [
      record.title_zh, record.title_original, record.summary_zh, record.source_name,
      ...(record.topics || []), ...(record.places || []).map(place => place.name_zh),
      ...organizationCodes(record), ...(record.event_tags || []),
      ...(record.country_codes || []).flatMap(item => [item.name_zh, item.alpha2, item.alpha3]),
    ].join(" ").toLowerCase();
    return record.quality?.passed !== false
      && (!query || haystack.includes(query))
      && (!topic || (record.topics || []).includes(topic))
      && (!organization || organizationCodes(record).includes(organization))
      && matchesCountry(record, country);
  });
  renderArchiveRows();
}

function renderArchiveRows() {
  const shown = state.filtered.slice(0, state.visible);
  $("resultCount").textContent = state.filtered.length;
  $("archiveList").innerHTML = shown.length ? shown.map(record => {
    const facts = [
      ...(record.numbers || []).slice(0, 2),
      ...(state.language === "en" ? (record.country_codes || []).slice(0, 2).map(country => country.alpha3) : (record.places || []).slice(0, 2).map(place => place.name_zh)),
      ...organizationCodes(record).slice(0, 2),
      ...(record.event_tags || []).slice(0, 1),
    ];
    return `<article class="archive-row">
      <div class="archive-date"><b>${esc(formatDate(record.published_at))}</b></div>
      <div class="archive-title"><h3>${esc(field(record, "title_zh", "title_original"))}</h3>${state.language === "en" ? "" : `<p>${esc(record.title_original)}</p>`}</div>
      <div class="archive-source"><b>${esc(record.source_name)}</b><span>${esc(state.language === "en" ? (state.mode === "energy" ? "Energy technology" : "Climate") : ((record.topics || []).slice(0, 2).join(" · ") || "气候动态"))}</span></div>
      <div class="archive-atoms">${facts.length ? facts.map(fact => `<i>${esc(fact)}</i>`).join("") : ""}<a href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">${esc(tr("source"))}</a></div>
    </article>`;
  }).join("") : `<div class="empty compact"><b>${state.language === "en" ? "No matching records" : "没有匹配记录"}</b><p>${state.language === "en" ? "Try fewer filters or a different search term." : "请减少筛选条件或更换关键词。"}</p></div>`;
  $("loadMore").hidden = state.visible >= state.filtered.length;
}

function svgEl(name, attrs = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function decodeArc(topology, arcIndex) {
  const reverse = arcIndex < 0;
  const source = topology.arcs[reverse ? ~arcIndex : arcIndex];
  const [scaleX, scaleY] = topology.transform.scale;
  const [translateX, translateY] = topology.transform.translate;
  let x = 0;
  let y = 0;
  const points = source.map(([deltaX, deltaY]) => {
    x += deltaX;
    y += deltaY;
    return [x * scaleX + translateX, y * scaleY + translateY];
  });
  return reverse ? points.reverse() : points;
}

function worldPoint([longitude, latitude]) {
  return [(longitude + 180) / 360 * 1000, (90 - latitude) / 180 * 500];
}

function centeredPoint(longitude, latitude) {
  const centerX = (MAP_CENTER_LON + 180) / 360 * 1000;
  const baseX = (longitude + 180) / 360 * 1000;
  return [((baseX - centerX + 500) % 1000 + 1000) % 1000, (90 - latitude) / 180 * 500];
}

function ringCoordinates(topology, refs) {
  const points = [];
  refs.forEach(ref => {
    const arc = decodeArc(topology, ref);
    points.push(...(points.length ? arc.slice(1) : arc));
  });
  return points;
}

function ringPath(topology, refs) {
  const points = ringCoordinates(topology, refs);
  return points.map((point, index) => {
    const [x, y] = worldPoint(point);
    const crossesEdge = index > 0 && Math.abs(point[0] - points[index - 1][0]) > 180;
    return `${index && !crossesEdge ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join("") + "Z";
}

function geometryPath(topology, geometry) {
  if (geometry.type === "Polygon") return geometry.arcs.map(ring => ringPath(topology, ring)).join("");
  if (geometry.type === "MultiPolygon") return geometry.arcs.flatMap(polygon => polygon.map(ring => ringPath(topology, ring))).join("");
  return "";
}

function spreadMarkerPositions(events) {
  const placed = [];
  return events.map((item, index) => {
    const origin = centeredPoint(Number(item.lon), Number(item.lat));
    let [x, y] = origin;
    let attempt = 0;
    while (placed.some(point => Math.hypot(point.x - x, point.y - y) < 19) && attempt < 40) {
      attempt += 1;
      const angle = index * 2.39996 + attempt * 1.618;
      const radius = 9 * Math.sqrt(attempt);
      x = Math.max(12, Math.min(988, origin[0] + Math.cos(angle) * radius));
      y = Math.max(12, Math.min(488, origin[1] + Math.sin(angle) * radius));
    }
    placed.push({ x, y });
    return { item, x, y, originX: origin[0], originY: origin[1] };
  });
}

async function renderMap(events) {
  const topology = state.mapTopology || await fetchJson(new URL("./assets/countries-110m.json", document.baseURI).href);
  state.mapTopology = topology;
  if (!topology?.objects?.countries?.geometries?.length) throw new Error("invalid map topology");
  const svg = $("worldMap");
  svg.replaceChildren();
  const countries = svgEl("g", { "aria-hidden": "true" });
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    if (path) countries.appendChild(svgEl("path", { d: path, class: "map-country", "fill-rule": "evenodd" }));
  });
  const shift = 500 - (MAP_CENTER_LON + 180) / 360 * 1000;
  const westernCopy = countries.cloneNode(true);
  const easternCopy = countries.cloneNode(true);
  westernCopy.setAttribute("transform", `translate(${shift},0)`);
  easternCopy.setAttribute("transform", `translate(${shift + 1000},0)`);
  svg.append(westernCopy, easternCopy);

  const [chinaX, chinaY] = centeredPoint(105, 35);
  svg.appendChild(svgEl("path", {
    d: `M${chinaX - 7},${chinaY}H${chinaX + 7}M${chinaX},${chinaY - 7}V${chinaY + 7}`,
    class: "china-anchor",
  }));
  const chinaLabel = svgEl("text", { x: chinaX + 11, y: chinaY + 5, class: "china-label" });
  chinaLabel.textContent = state.language === "en" ? "China" : "中国";
  svg.appendChild(chinaLabel);

  spreadMarkerPositions(events).forEach(({ item, x, y, originX, originY }, index) => {
    const longitude = Number(item.lon);
    const latitude = Number(item.lat);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;
    if (Math.hypot(x - originX, y - originY) > 4) {
      svg.appendChild(svgEl("line", { x1: originX, y1: originY, x2: x, y2: y, class: "event-stem" }));
    }
    const pin = svgEl("g", {
      class: "event-pin", tabindex: "0", role: "button", "data-marker": item.marker_id,
      "aria-label": `${item.place}：${field(item, "title_zh", "title_original")}`,
    });
    pin.append(
      svgEl("circle", { cx: x, cy: y, r: 13, class: "event-halo" }),
      svgEl("circle", { cx: x, cy: y, r: 6.5, class: "event-marker" }),
    );
    pin.addEventListener("click", () => selectMapEvent(item));
    pin.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") selectMapEvent(item);
    });
    pin.addEventListener("mouseenter", event => showMapTooltip(event, item));
    pin.addEventListener("mouseleave", () => $("mapTooltip").classList.remove("show"));
    svg.appendChild(pin);
    if (index === 0) selectMapEvent(item);
  });
  $("mapLoading").hidden = true;
  $("mapCanvas").classList.add("map-ready");
}

function showMapTooltip(event, item) {
  const tooltip = $("mapTooltip");
  const bounds = $("mapCanvas").getBoundingClientRect();
  const record = findArchiveRecord(item);
  const place = state.language === "en" ? ((record.country_codes || []).map(country => country.alpha3).join(" · ") || "Global") : item.place;
  tooltip.innerHTML = `<b>${esc(place)} · ${esc(state.language === "en" ? (state.mode === "energy" ? "Energy technology" : "Climate") : item.theme)}</b><span>${esc(field(record, "title_zh", "title_original"))}</span>`;
  tooltip.style.left = `${Math.min(bounds.width - 280, Math.max(12, event.clientX - bounds.left + 12))}px`;
  tooltip.style.top = `${Math.max(12, event.clientY - bounds.top - 80)}px`;
  tooltip.classList.add("show");
}

function selectMapEvent(item) {
  const record = findArchiveRecord(item);
  const place = state.language === "en" ? ((record.country_codes || []).map(country => country.alpha3).join(" · ") || "Global") : item.place;
  const theme = state.language === "en" ? (state.mode === "energy" ? "Energy technology" : "Climate") : item.theme;
  $("mapDetail").innerHTML = `<span>${esc(place)} · ${esc(theme)}</span><h2>${esc(field(record, "title_zh", "title_original"))}</h2>${summaryOrAtoms(record)}<small>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</small><a href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">${esc(tr("source"))}</a>`;
}

function renderMapPlaces(events) {
  $("mapPlaceList").innerHTML = events.length
    ? events.map(item => `<button type="button" data-map-id="${esc(item.marker_id)}"><i></i>${esc(item.place)}<span>${esc(item.theme)}</span></button>`).join("")
    : `<span>${state.mapPeriod === "today" ? "今日队列" : "本周"}暂无带有明确地理位置的新记录。</span>`;
  document.querySelectorAll("[data-map-id]").forEach(button => button.addEventListener("click", () => {
    const item = events.find(event => event.marker_id === button.dataset.mapId);
    if (item) selectMapEvent(item);
  }));
}

function mapEventsFor(period) {
  if (period === "week") return state.dashboard.map_events_week || [];
  return state.dashboard.map_events_today || state.dashboard.map_events || [];
}

async function switchMapPeriod(period) {
  state.mapPeriod = period;
  document.querySelectorAll("[data-map-period]").forEach(button => {
    const active = button.dataset.mapPeriod === period;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const events = mapEventsFor(period);
  $("mapRangeNote").textContent = period === "today" ? tr("todayQueue") : tr("thisWeek");
  renderMapPlaces(events);
  await renderMap(events);
}

function setupMapPeriods() {
  updateMapPeriodCounts();
  document.querySelectorAll("[data-map-period]").forEach(button => {
    button.addEventListener("click", () => switchMapPeriod(button.dataset.mapPeriod).catch(error => {
      console.error("Map period switch failed", error);
      toast("地图切换失败，请刷新页面重试。");
    }));
  });
}

function updateMapPeriodCounts() {
  const todayEvents = mapEventsFor("today");
  const weekEvents = mapEventsFor("week");
  $("todayMapCount").textContent = todayEvents.length;
  $("weekMapCount").textContent = weekEvents.length;
}

function companyTypeLabel(type) {
  if (type === "energy_startup") return state.language === "en" ? "Energy start-up" : "能源初创企业";
  if (type === "energy_company") return state.language === "en" ? "Energy company" : "能源企业";
  return state.language === "en" ? "Energy major or sector leader" : "能源巨头与龙头企业";
}

function setupCompanyIntelligence() {
  if (!state.companyData) return;
  const countries = [...new Set((state.companyData.companies || []).map(company => company.country))]
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  $("companyCountryFilter").innerHTML = `<option value="">${esc(tr("allCountries"))}</option>`
    + countries.map(country => `<option value="${esc(country)}">${esc(country)}</option>`).join("");
  ["companySearch", "companyTypeFilter", "companyCountryFilter"].forEach(id => {
    const element = $(id);
    if (!element) return;
    element.addEventListener(id === "companySearch" ? "input" : "change", () => {
      state.companyVisible = 12;
      applyCompanyFilters();
    });
  });
  $("companyLoadMore")?.addEventListener("click", () => {
    state.companyVisible += 12;
    renderCompanyCards();
  });
  document.querySelectorAll("[data-company-map-period]").forEach(button => {
    button.addEventListener("click", () => switchCompanyMapPeriod(button.dataset.companyMapPeriod).catch(error => {
      console.error("Company map period switch failed", error);
      toast(state.language === "en" ? "Unable to switch the company map." : "企业地图切换失败，请稍后重试。");
    }));
  });
  renderSpotlights();
}

function renderCompanyIntelligence() {
  const data = state.companyData;
  if (!data) return;
  const stats = data.statistics || {};
  $("companyScopeNote").textContent = state.language === "en" ? tr("companyScope") : (data.meta?.scope_note_zh || tr("companyScope"));
  $("companyKpis").innerHTML = (state.language === "en" ? [
    ["Companies", stats.companies || 0, `${formatCount(stats.traceable_basic_profiles || 0)} traceable profiles`],
    ["Majors and leaders", stats.majors || 0, "Projects, capacity and international presence"],
    ["Start-ups", stats.startups || 0, "Technology and commercialisation"],
    ["Countries", stats.countries || 0, "Headquarters basis"],
    ["Linked intelligence", stats.intelligence || 0, `${stats.detailed_profiles || 0} detailed profiles`],
  ] : [
    ["企业样本", stats.companies || 0, `可追溯基础档案 ${formatCount(stats.traceable_basic_profiles || 0)} 家`],
    ["能源巨头与龙头", stats.majors || 0, "项目、产能与跨国布局"],
    ["能源初创企业", stats.startups || 0, "技术路线与商业化进展"],
    ["覆盖国家", stats.countries || 0, "总部口径"],
    ["关联企业情报", stats.intelligence || 0, `深度档案 ${stats.detailed_profiles || 0} 家`],
  ]).map(([label, value, note]) => `<article><span>${esc(label)}</span><b>${formatCount(value)}</b><small>${esc(note)}</small></article>`).join("");
  applyCompanyFilters();
  $("companyTodayMapCount").textContent = (data.map_events_today || []).length;
  $("companyWeekMapCount").textContent = (data.map_events_week || []).length;
  switchCompanyMapPeriod(state.companyMapPeriod).catch(error => console.error("Company map failed", error));
}

function applyCompanyFilters() {
  const data = state.companyData;
  if (!data) return;
  const query = $("companySearch")?.value.trim().toLowerCase() || "";
  const type = $("companyTypeFilter")?.value || "";
  const country = $("companyCountryFilter")?.value || "";
  state.companyFiltered = (data.companies || []).filter(company => {
    const haystack = [company.name_zh, company.name_en, company.country, company.continent,
      company.overview_zh, company.strategy_zh, ...(company.business_zh || []),
      ...(company.core_technologies_zh || []),
      ...(company.key_projects || []).flatMap(project => [project.name_zh, project.location_zh, project.status_zh]),
    ].join(" ").toLowerCase();
    return (!query || haystack.includes(query)) && (!type || company.type === type) && (!country || company.country === country);
  }).sort((left, right) => Number(right.intelligence_count || 0) - Number(left.intelligence_count || 0)
    || left.name_zh.localeCompare(right.name_zh, "zh-CN"));
  renderCompanyCards();
}

function financialValue(metric, currency) {
  if (!metric || metric.value === null || metric.value === undefined) return state.language === "en" ? "Not disclosed" : "未公开";
  const symbols = { USD: "$", EUR: "€", CNY: "¥", GBP: "£", SAR: "SAR " };
  const units = state.language === "en" ? { billion: "bn", million: "m" } : { billion: "十亿", million: "百万" };
  const value = Number(metric.value);
  return `${symbols[currency] || `${currency} `}${Number.isFinite(value) ? value.toLocaleString(state.language === "en" ? "en-GB" : "zh-CN") : metric.value}${units[metric.unit] || metric.unit || ""}`;
}

function companyProfileHtml(company) {
  const finance = company.financials;
  const financeHtml = finance ? `<div class="company-finance">
    <div><span>${esc(state.language === "en" ? "Revenue" : (finance.revenue?.label_zh || "营业收入"))}</span><b>${esc(financialValue(finance.revenue, finance.currency))}</b></div>
    <div><span>${esc(state.language === "en" ? "Net profit" : (finance.profit?.label_zh || "净利润"))}</span><b>${esc(financialValue(finance.profit, finance.currency))}</b></div>
    <small>${esc(state.language === "en" ? `FY ${finance.fiscal_year || "latest"} · company-reported basis` : `${finance.fiscal_year || "最新"}财年 · ${finance.note_zh || "以企业披露口径为准"}`)}</small>
  </div>` : "";
  const technologies = (state.language === "en" ? (company.core_technologies_en || []) : (company.core_technologies_zh || [])).map(item => `<i>${esc(item)}</i>`).join("");
  const projects = (company.key_projects || []).map(project => `<li><b>${esc(state.language === "en" ? (project.name_en || project.name_zh) : project.name_zh)}</b><span>${esc(state.language === "en" ? (project.location_en || project.location_zh || "") : (project.location_zh || ""))}</span><p>${esc(state.language === "en" ? (project.status_en || "") : (project.status_zh || ""))}</p></li>`).join("");
  const sources = (company.profile_sources || []).map(source => `<a href="${esc(safeUrl(source.url))}" target="_blank" rel="noopener noreferrer">${esc(state.language === "en" ? (source.label_en || "Source") : source.label_zh)} ↗</a>`).join("");
  const strategy = state.language === "en" ? (company.strategy_en || "") : company.strategy_zh;
  if (!financeHtml && !technologies && !projects && !strategy) return "";
  return `<details class="company-profile"><summary>${state.language === "en" ? "Full company profile" : "查看完整企业档案"}</summary>
    ${financeHtml}
    ${technologies ? `<div class="company-profile-block"><b>${state.language === "en" ? "Core technologies" : "核心技术"}</b><div class="company-business">${technologies}</div></div>` : ""}
    ${projects ? `<div class="company-profile-block"><b>${state.language === "en" ? "Key projects" : "重点项目"}</b><ul>${projects}</ul></div>` : ""}
    ${strategy ? `<div class="company-profile-block"><b>${state.language === "en" ? "Direction" : "发展方向"}</b><p>${esc(strategy)}</p></div>` : ""}
    ${sources ? `<div class="company-profile-sources">${sources}</div>` : ""}
  </details>`;
}

function renderCompanyCards() {
  const shown = state.companyFiltered.slice(0, state.companyVisible);
  $("companyResultCount").textContent = state.companyFiltered.length;
  $("companyList").innerHTML = shown.length ? shown.map(company => {
    const latest = (company.latest_intelligence || [])[0];
    const primaryName = state.language === "en" ? (company.name_en || company.name_zh) : company.name_zh;
    const secondaryName = state.language === "en" ? company.name_zh : company.name_en;
    const overview = state.language === "en" ? (company.overview_en || "") : company.overview_zh;
    const business = state.language === "en" ? (company.business_en || []) : (company.business_zh || []);
    return `<article class="company-card">
      <div class="company-card-head"><span>${esc(companyTypeLabel(company.type))}</span><small>${esc(company.country)} · ${esc(company.continent)}</small></div>
      <h4>${esc(primaryName)}</h4><p class="company-name-en">${esc(secondaryName)}</p>
      ${overview ? `<p class="company-overview">${esc(overview)}</p>` : ""}
      <div class="company-business">${business.map(item => `<i>${esc(item)}</i>`).join("")}</div>
      ${companyProfileHtml(company)}
      ${latest ? `<div class="company-latest"><b>${state.language === "en" ? "Latest linked intelligence" : "最新关联情报"}</b><a href="${esc(safeUrl(latest.canonical_url))}" target="_blank" rel="noopener noreferrer">${esc(state.language === "en" ? (latest.title_original || latest.title_zh) : latest.title_zh)} ↗</a><small>${esc(formatDate(latest.published_at))}${state.language === "en" ? "" : ` · ${esc(latest.category_zh)}`}</small></div>` : `<div class="company-latest empty-state"><b>${state.language === "en" ? "No linked news yet" : "暂无站内关联动态"}</b><small>${state.language === "en" ? "The profile is retained and future news will be linked automatically." : "企业基础资料保留，后续新闻将自动关联。"}</small></div>`}
      ${company.website ? `<a class="company-site" href="${esc(safeUrl(company.website))}" target="_blank" rel="noopener noreferrer">${state.language === "en" ? "Company website" : "企业官网"} ↗</a>` : `<span class="company-site">${state.language === "en" ? "Sources: linked news" : "资料来源：关联新闻原文"}</span>`}
    </article>`;
  }).join("") : `<div class="empty compact"><b>${state.language === "en" ? "No matching companies" : "没有匹配企业"}</b><p>${state.language === "en" ? "Try fewer filters or another business term." : "请减少筛选条件或更换业务关键词。"}</p></div>`;
  $("companyLoadMore").hidden = state.companyVisible >= state.companyFiltered.length;
}

function companyMapEvents(period) {
  if (!state.companyData) return [];
  return period === "week" ? (state.companyData.map_events_week || []) : (state.companyData.map_events_today || []);
}

function selectCompanyMapEvent(item) {
  const record = findArchiveRecord(item);
  const place = state.language === "en" ? ((record.country_codes || []).map(country => country.alpha3).join(" · ") || "Global") : item.place;
  $("companyMapDetail").innerHTML = `<span>${esc(place)} · ${esc(state.language === "en" ? "Company intelligence" : item.theme)}</span><h2>${esc(field(record, "title_zh", "title_original"))}</h2>
    <p class="company-event-companies">${state.language === "en" ? "Companies" : "涉及企业"}：${esc((item.companies || []).join("、"))}</p>
    ${summaryOrAtoms(record)}<small>${state.language === "en" ? "Source-linked location" : esc(item.location_basis_zh || "新闻明确地点")} · ${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</small>
    <a href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">${esc(tr("source"))}</a>`;
}

function showCompanyMapTooltip(event, item) {
  const tooltip = $("companyMapTooltip");
  const bounds = $("companyMapCanvas").getBoundingClientRect();
  const record = findArchiveRecord(item);
  const place = state.language === "en" ? ((record.country_codes || []).map(country => country.alpha3).join(" · ") || "Global") : item.place;
  tooltip.innerHTML = `<b>${esc(place)} · ${esc((item.companies || []).join("、"))}</b><span>${esc(field(record, "title_zh", "title_original"))}</span>`;
  tooltip.style.left = `${Math.min(bounds.width - 280, Math.max(12, event.clientX - bounds.left + 12))}px`;
  tooltip.style.top = `${Math.max(12, event.clientY - bounds.top - 80)}px`;
  tooltip.classList.add("show");
}

async function renderCompanyMap(events) {
  const topology = state.mapTopology || await fetchJson(new URL("./assets/countries-110m.json", document.baseURI).href);
  state.mapTopology = topology;
  if (!topology?.objects?.countries?.geometries?.length) throw new Error("invalid map topology");
  const svg = $("companyWorldMap");
  svg.replaceChildren();
  const countries = svgEl("g", { "aria-hidden": "true" });
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    if (path) countries.appendChild(svgEl("path", { d: path, class: "map-country", "fill-rule": "evenodd" }));
  });
  const shift = 500 - (MAP_CENTER_LON + 180) / 360 * 1000;
  const westernCopy = countries.cloneNode(true);
  const easternCopy = countries.cloneNode(true);
  westernCopy.setAttribute("transform", `translate(${shift},0)`);
  easternCopy.setAttribute("transform", `translate(${shift + 1000},0)`);
  svg.append(westernCopy, easternCopy);
  spreadMarkerPositions(events).forEach(({ item, x, y, originX, originY }) => {
    if (Math.hypot(x - originX, y - originY) > 4) svg.appendChild(svgEl("line", { x1: originX, y1: originY, x2: x, y2: y, class: "event-stem" }));
    const pin = svgEl("g", { class: "event-pin", tabindex: "0", role: "button", "aria-label": `${item.place}：${item.title_zh}` });
    pin.append(svgEl("circle", { cx: x, cy: y, r: 13, class: "event-halo" }), svgEl("circle", { cx: x, cy: y, r: 6.5, class: "event-marker" }));
    pin.addEventListener("click", () => selectCompanyMapEvent(item));
    pin.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") selectCompanyMapEvent(item); });
    pin.addEventListener("mouseenter", event => showCompanyMapTooltip(event, item));
    pin.addEventListener("mouseleave", () => $("companyMapTooltip").classList.remove("show"));
    svg.appendChild(pin);
  });
  if (events[0]) selectCompanyMapEvent(events[0]);
  $("companyMapLoading").hidden = true;
  $("companyMapCanvas").classList.add("map-ready");
}

async function switchCompanyMapPeriod(period) {
  state.companyMapPeriod = period === "week" ? "week" : "today";
  document.querySelectorAll("[data-company-map-period]").forEach(button => {
    const active = button.dataset.companyMapPeriod === state.companyMapPeriod;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const events = companyMapEvents(state.companyMapPeriod);
  $("companyMapPlaceList").innerHTML = events.length
    ? events.map(item => `<button type="button" data-company-map-id="${esc(item.marker_id)}"><i></i>${esc(item.place)}<span>${esc((item.companies || []).join("、"))}</span></button>`).join("")
    : `<span>${state.companyMapPeriod === "today" ? "今日队列" : "本周"}暂无可定位的企业情报；系统不会为填满地图而猜测项目地点。</span>`;
  document.querySelectorAll("[data-company-map-id]").forEach(button => button.addEventListener("click", () => {
    const item = events.find(event => event.marker_id === button.dataset.companyMapId);
    if (item) selectCompanyMapEvent(item);
  }));
  await renderCompanyMap(events);
}

function setupEnergyReports() {
  if (!state.reportData) return;
  const filters = state.reportData.filters || {};
  $("energyReportCountry").innerHTML = `<option value="">${esc(tr("allCountryOrganizations"))}</option>`
    + (filters.countries_or_regions || []).map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
  $("energyReportYear").innerHTML = `<option value="">${esc(tr("allYears"))}</option>`
    + (filters.years || []).map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
  ["energyReportSearch", "energyResourceType", "energyReportCountry", "energyReportOrganization", "energyReportYear"].forEach(id => {
    $(id)?.addEventListener(id === "energyReportSearch" ? "input" : "change", () => {
      state.reportVisible = 12;
      applyEnergyReportFilters();
    });
  });
  $("energyReportLoadMore")?.addEventListener("click", () => {
    state.reportVisible += 12;
    renderEnergyReportCards();
  });
}

function renderEnergyReports() {
  const data = state.reportData;
  if (!data) return;
  const stats = data.statistics || {};
  $("energyReportKpis").innerHTML = (state.language === "en" ? [
    ["Reports", stats.reports || 0], ["Databases", stats.databases || 0], ["Publishers", stats.publishers || 0], ["With abstracts", stats.with_abstract || 0],
  ] : [
    ["报告记录", stats.reports || 0], ["能源数据库", stats.databases || 0], ["发布机构", stats.publishers || 0], ["含摘要信息", stats.with_abstract || 0],
  ]).map(([label, value]) => `<article><span>${esc(label)}</span><b>${esc(value)}</b></article>`).join("");
  $("energyReportNote").textContent = state.language === "en"
    ? `Official, traceable reports and databases. Data version: ${formatDate(data.meta?.updated_at, true)}`
    : `${data.meta?.selection_note_zh || ""} 数据版本：${formatDate(data.meta?.updated_at, true)}`;
  applyEnergyReportFilters();
}

function balanceReportPublishers(rows) {
  const buckets = new Map();
  rows.forEach(row => {
    const key = row.publisher || "未标注机构";
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(row);
  });
  const output = [];
  while ([...buckets.values()].some(bucket => bucket.length)) {
    [...buckets.values()].forEach(bucket => { if (bucket.length) output.push(bucket.shift()); });
  }
  return output;
}

function applyEnergyReportFilters() {
  if (!state.reportData) return;
  const query = $("energyReportSearch")?.value.trim().toLowerCase() || "";
  const resourceType = $("energyResourceType")?.value || "";
  const country = $("energyReportCountry")?.value || "";
  const organization = $("energyReportOrganization")?.value || "";
  const year = $("energyReportYear")?.value || "";
  const reports = (state.reportData.reports || []).map(report => ({ ...report, record_type: "能源报告" }));
  const databases = (state.reportData.databases || []).map(database => ({ ...database, record_type: "能源数据库" }));
  const filtered = [...reports, ...databases].filter(report => {
    const haystack = [report.title_zh, report.title_original, report.summary_zh, report.abstract_original, report.publisher,
      report.country_or_region, report.name_zh, report.name_original, report.maintainer, report.domain, report.core_data,
      report.primary_use, report.coverage, report.update_note, ...(report.topics || []),
      ...organizationCodes(report), ...(report.event_tags || []),
      ...(report.country_codes || []).flatMap(item => [item.name_zh, item.alpha2, item.alpha3])].join(" ").toLowerCase();
    return (!query || haystack.includes(query))
      && (!resourceType || report.record_type === resourceType)
      && (!country || (report.record_type === "能源报告" && report.country_or_region === country))
      && (!organization || organizationCodes(report).includes(organization))
      && (!year || (report.record_type === "能源报告" && String(report.year) === year));
  });
  state.reportFiltered = [
    ...balanceReportPublishers(filtered.filter(row => row.record_type === "能源报告")),
    ...filtered.filter(row => row.record_type === "能源数据库"),
  ];
  renderEnergyReportCards();
}

function renderEnergyReportCards() {
  const shown = state.reportFiltered.slice(0, state.reportVisible);
  $("energyReportResultCount").textContent = state.reportFiltered.length;
  $("energyReportList").innerHTML = shown.length ? shown.map(report => report.record_type === "能源数据库" ? `<article class="report-card database-card">
    <div class="report-card-meta"><span>${esc(report.domain)}</span><b>${state.language === "en" ? "Energy database" : "能源数据库"}</b></div>
    <h3><a href="${esc(safeUrl(report.database_url))}" target="_blank" rel="noopener noreferrer">${esc(state.language === "en" ? (report.name_original || report.name_zh) : report.name_zh)} →</a></h3>
    ${state.language === "en" ? (report.name_zh && report.name_zh !== report.name_original ? `<p class="report-title-original">${esc(report.name_zh)}</p>` : "") : `<p class="report-title-original">${esc(report.name_original)}</p>`}
    ${state.language === "en" ? "" : `<p class="report-summary">${esc(report.core_data)}</p>`}
    <div class="report-tags">${state.language === "en" ? "" : `<i>${esc(report.primary_use)}</i><i>${esc(report.update_note)}</i>`}${[...organizationCodes(report).slice(0, 2), ...(report.country_codes || []).slice(0, 2).map(item => item.alpha3)].map(tag => `<i>${esc(tag)}</i>`).join("")}</div>
    <footer><span>${esc(report.maintainer)}</span><small>${esc(report.coverage)}</small></footer>
  </article>` : `<article class="report-card">
    <div class="report-card-meta"><span>${esc(report.country_or_region)}</span><b>${esc(report.year)}</b></div>
    <h3><a href="${esc(safeUrl(report.report_url))}" target="_blank" rel="noopener noreferrer">${esc(state.language === "en" ? (report.title_original || report.title_zh) : report.title_zh)} ↗</a></h3>
    ${state.language === "en" ? (report.title_zh && report.title_zh !== report.title_original ? `<p class="report-title-original">${esc(report.title_zh)}</p>` : "") : `<p class="report-title-original">${esc(report.title_original)}</p>`}
    ${state.language === "en" ? (report.abstract_original ? `<p class="report-summary">${esc(report.abstract_original)}</p>` : "") : (substantiveSummary(report.summary_zh) ? `<p class="report-summary">${esc(report.summary_zh)}</p>` : "")}
    <div class="report-tags">${[...(report.topics || []), ...organizationCodes(report), ...(report.event_tags || []), ...(report.country_codes || []).map(item => item.alpha3)].slice(0, 7).map(topic => `<i>${esc(topic)}</i>`).join("")}</div>
    <footer><span>${esc(report.publisher)}</span><small>${esc(report.language)} · ${esc(formatDate(report.published_at))}${report.access_note_zh ? ` · ${esc(report.access_note_zh)}` : ""}</small></footer>
  </article>`).join("") : `<div class="empty compact"><b>${state.language === "en" ? "No matching resources" : "没有匹配资源"}</b><p>${state.language === "en" ? "Try fewer filters or another search term." : "请减少筛选条件或更换检索词。"}</p></div>`;
  $("energyReportLoadMore").hidden = state.reportVisible >= state.reportFiltered.length;
}

const COUNTRY_CONCEPTS = [
  { name: "中国", terms: ["中国", "北京", "china", "chinese", "beijing"] },
  { name: "美国", terms: ["美国", "美方", "united states", "u.s.", "usa", "american", "north america", "texas", "california", "oregon", "new york", "michigan", "new england"] },
  { name: "欧盟", terms: ["欧盟", "欧洲", "europe", "european union", "eu"] },
  { name: "拉丁美洲", terms: ["拉丁美洲", "南美", "巴西", "亚马孙", "latin america", "brazil", "amazon"] },
  { name: "非洲", terms: ["非洲", "南非", "肯尼亚", "乌干达", "africa", "south africa", "kenya", "uganda"] },
  { name: "澳大利亚及太平洋", terms: ["澳大利亚", "太平洋", "大洋洲", "australia", "pacific", "oceania"] },
  { name: "南极洲", terms: ["南极", "南极洲", "antarctic", "antarctica"] },
];

const TOPIC_CONCEPTS = [
  { name: "气候资金", terms: ["气候资金", "资金", "融资", "finance", "fund", "loss and damage"] },
  { name: "能源与排放", terms: ["能源", "减排", "排放", "化石燃料", "可再生能源", "emission", "energy", "renewable", "fossil"] },
  { name: "气候适应", terms: ["适应", "韧性", "损失损害", "adaptation", "resilience"] },
  { name: "碳市场", terms: ["碳市场", "碳交易", "article 6", "carbon market", "carbon credit"] },
  { name: "极端天气", terms: ["极端天气", "高温", "洪水", "干旱", "野火", "飓风", "heat", "flood", "drought", "wildfire", "hurricane"] },
  { name: "国际谈判", terms: ["谈判", "cop31", "unfccc", "ndc", "全球盘点", "climate talks"] },
];

function recordText(record) {
  return [
    record.title_zh, record.title_original, record.summary_zh, record.why_zh, record.source_name,
    ...(record.topics || []), ...(record.places || []).map(place => place.name_zh),
  ].filter(Boolean).join(" ").toLowerCase();
}

function recordsInLatestWeek(items) {
  const latestDay = items.map(item => beijingDay(item.published_at)).filter(Boolean).sort().at(-1);
  if (!latestDay) return [];
  const latestTime = new Date(`${latestDay}T00:00:00+08:00`).getTime();
  return items.filter(record => {
    const value = new Date(record.published_at).getTime();
    return Number.isFinite(value) && value >= latestTime - 6 * 86400000 && value < latestTime + 86400000;
  });
}

function termMatches(text, term) {
  const normalized = text.toLowerCase();
  if (/[a-z]/.test(term) && !/[\u4e00-\u9fff]/.test(term)) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(normalized);
  }
  return normalized.includes(term);
}

function detectConcepts(text, concepts) {
  return concepts.filter(concept => concept.terms.some(term => termMatches(text, term)));
}

function planQuestion(query) {
  const normalized = query.toLowerCase().replace(/[？?！，。；：、]/g, " ");
  let entities = detectConcepts(normalized, COUNTRY_CONCEPTS);
  if (/中美|美中/.test(normalized)) {
    entities = COUNTRY_CONCEPTS.filter(concept => ["中国", "美国"].includes(concept.name));
  }
  const topics = detectConcepts(normalized, TOPIC_CONCEPTS);
  const isFollowUp = /这些|上述|其中|前述|继续|它们|前者|后者|第[一二三四五六七八12345678]条/.test(normalized);
  let scope = /今日|今天|当天/.test(normalized) ? "today"
    : (/本周|一周|近七天|最近7天/.test(normalized) ? "week" : "archive");
  if (isFollowUp && state.assistant.lastPlan && !/今日|今天|当天|本周|一周|近七天|最近7天|历史|档案/.test(normalized)) {
    scope = state.assistant.lastPlan.scope;
  }
  const intent = /比较|对比|差异|异同|中美|美中/.test(normalized) ? "compare"
    : (/趋势|演变|变化|进展|时间线/.test(normalized) ? "trend"
      : (/意味着|影响|含义|谈判|政策|风险|启示/.test(normalized) ? "implication"
        : (/简报|重点|概览|综述/.test(normalized) ? "brief" : "search")));
  const countMatch = normalized.match(/(\d+)\s*(?:条|项|个)/);
  const limit = Math.max(1, Math.min(8, countMatch ? Number(countMatch[1]) : (intent === "brief" ? 6 : 5)));
  const generic = /请|给出|告诉我|哪些|有什么|值得关注|气候|情报|近期|最近|今日|今天|当天|简报|本周|一周|近七天|最近7天|信息|动态|比较|对比|趋势|政策|影响|的|和|与|中/g;
  const residue = normalized.replace(generic, " ");
  const rawTerms = [
    ...(residue.match(/[a-z][a-z0-9.-]{2,}/g) || []),
    ...(residue.match(/[\u4e00-\u9fff]{2,8}/g) || []),
  ];
  const terms = [...new Set([
    ...entities.flatMap(concept => concept.terms),
    ...topics.flatMap(concept => concept.terms),
    ...rawTerms,
  ])].filter(term => term.length > 1);
  return { query, normalized, entities, topics, scope, intent, limit, terms, isFollowUp };
}

function recordMatchesConcept(record, concept) {
  const text = recordText(record);
  return concept.terms.some(term => termMatches(text, term));
}

function scopedRecords(plan) {
  const all = state.archive.records || [];
  if (plan.isFollowUp && state.assistant.lastRecords.length) return state.assistant.lastRecords;
  if (plan.scope === "today") return state.dashboard.intelligence || [];
  if (plan.scope === "week") return recordsInLatestWeek(all);
  return all;
}

function scoreRecord(record, plan) {
  const titleZh = String(record.title_zh || "").toLowerCase();
  const titleOriginal = String(record.title_original || "").toLowerCase();
  const summary = String(record.summary_zh || "").toLowerCase();
  const source = String(record.source_name || "").toLowerCase();
  const topicText = (record.topics || []).join(" ").toLowerCase();
  const placeText = (record.places || []).map(place => place.name_zh).join(" ").toLowerCase();
  const entityHits = plan.entities.filter(concept => recordMatchesConcept(record, concept)).length;
  const topicHits = plan.topics.filter(concept => recordMatchesConcept(record, concept)).length;
  // A follow-up already operates on the previous evidence set. New words such
  // as “谈判含义” describe the requested analysis and must not discard those
  // records merely because their taxonomy lacks the same literal label.
  if (!plan.isFollowUp && plan.entities.length && !entityHits) return -1;
  if (!plan.isFollowUp && plan.topics.length && !topicHits) return -1;
  let score = Number(record.relevance_score || 0) / 4 + entityHits * 34 + topicHits * 26;
  plan.terms.forEach(term => {
    if (termMatches(titleZh, term)) score += 14;
    if (termMatches(titleOriginal, term)) score += 10;
    if (termMatches(topicText, term) || termMatches(placeText, term)) score += 12;
    if (termMatches(summary, term)) score += 5;
    if (termMatches(source, term)) score += 2;
  });
  return score;
}

function selectEvidence(plan) {
  const candidates = scopedRecords(plan);
  const ranked = candidates.map(record => ({ record, score: scoreRecord(record, plan) }))
    .filter(item => item.score >= 0)
    .sort((left, right) => right.score - left.score
      || String(right.record.published_at).localeCompare(String(left.record.published_at)));
  const selected = [];
  const sourceCounts = new Map();
  const add = record => {
    if (selected.some(item => item.record_id === record.record_id || item.canonical_url === record.canonical_url)) return;
    const source = record.source_name || record.source_id;
    if ((sourceCounts.get(source) || 0) >= 2) return;
    selected.push(record);
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
  };
  if (plan.intent === "compare" && plan.entities.length > 1) {
    plan.entities.forEach(concept => ranked
      .filter(item => recordMatchesConcept(item.record, concept))
      .slice(0, Math.max(2, Math.ceil(plan.limit / plan.entities.length)))
      .forEach(item => add(item.record)));
  }
  ranked.forEach(item => { if (selected.length < plan.limit) add(item.record); });
  return { records: selected.slice(0, plan.limit), candidateCount: candidates.length };
}

function scopeLabel(scope) {
  return scope === "today" ? `最新完整日（${state.dashboard.meta?.date || "待核"}，单日约10条）`
    : (scope === "week" ? "最近七个自然日" : "站内滚动档案");
}

function intentLabel(intent) {
  return ({ brief: "简报归纳", compare: "样本比较", trend: "时间线", implication: "政策含义", search: "证据检索" })[intent];
}

function planHtml(plan, records) {
  const region = plan.entities.length ? plan.entities.map(item => item.name).join(" / ") : "不限地区";
  const topic = plan.topics.length ? plan.topics.map(item => item.name).join(" / ") : "综合议题";
  return `<div class="chat-plan"><span>${esc(scopeLabel(plan.scope))}</span><span>${esc(region)}</span><span>${esc(topic)}</span><span>${esc(intentLabel(plan.intent))} · ${records.length} 条证据</span></div>`;
}

function evidenceList(records, { showWhy = false, chronological = false } = {}) {
  const ordered = chronological
    ? [...records].sort((a, b) => String(a.published_at).localeCompare(String(b.published_at)))
    : records;
  return `<ol class="evidence-list">${ordered.map((record, index) => `<li>
    <b>${chronological ? esc(formatDate(record.published_at)) + " · " : ""}${esc(record.title_zh || record.title_original)}</b>
    <p>${esc(record.summary_zh || "该条目尚无合格中文摘要。")}</p>
    ${showWhy && record.why_zh ? `<p class="evidence-implication"><strong>关注含义：</strong>${esc(record.why_zh)}</p>` : ""}
    <small>[${index + 1}] ${esc(record.source_name)} · ${esc(formatDate(record.published_at))}</small>
    <a href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">核验原文 ↗</a>
  </li>`).join("")}</ol>`;
}

function topTopics(records) {
  const counts = new Map();
  records.flatMap(record => record.topics || []).forEach(topic => counts.set(topic, (counts.get(topic) || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(item => item[0]).join("、") || "综合气候议题";
}

function comparisonHtml(plan, records) {
  return `<div class="chat-analysis"><h4>样本对比</h4>${plan.entities.map(concept => {
    const group = records.filter(record => recordMatchesConcept(record, concept));
    return `<p><strong>${esc(concept.name)}：</strong>${group.length
      ? `检索到 ${group.length} 条，主要涉及 ${esc(topTopics(group))}。`
      : "当前时间范围内没有足够的站内证据。"}</p>`;
  }).join("")}<p>这是对本站当前样本的比较，不代表两国全部气候行动的强弱排序。</p></div>`;
}

function addChatMessage(role, html) {
  const article = document.createElement("article");
  article.className = `chat-message ${role}`;
  article.innerHTML = `<span>${role === "user" ? "您" : "情报助手"}</span><div>${html}</div>`;
  $("chatLog").appendChild(article);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

function answerQuestion(query) {
  addChatMessage("user", `<p>${esc(query)}</p>`);
  const plan = planQuestion(query);
  const { records, candidateCount } = selectEvidence(plan);
  if (!records.length) {
    addChatMessage("assistant", `${planHtml(plan, records)}<p>在${esc(scopeLabel(plan.scope))}的 ${candidateCount} 条候选记录中，没有找到同时满足地区和议题条件的证据。您可以放宽时间范围或去掉一个限定词；系统不会用档案外常识补写答案。</p>`);
    return;
  }
  let analysis = `<p>在${esc(scopeLabel(plan.scope))}中，筛出 ${records.length} 条高相关证据，主要涉及 ${esc(topTopics(records))}。</p>`;
  if (plan.intent === "compare" && plan.entities.length > 1) analysis += comparisonHtml(plan, records);
  if (plan.intent === "trend") analysis += "<div class=\"chat-analysis\"><h4>时间线读法</h4><p>以下按发布时间排列，可用于观察议题推进顺序；记录数量不足时，不据此声称长期趋势已经形成。</p></div>";
  if (plan.intent === "implication") analysis += "<div class=\"chat-analysis\"><h4>政策含义</h4><p>先列来源陈述，再列系统归纳的关注含义；后者是辅助判断，不是原文事实。</p></div>";
  const evidence = evidenceList(records, {
    showWhy: plan.intent === "implication",
    chronological: plan.intent === "trend",
  });
  addChatMessage("assistant", `${planHtml(plan, records)}${analysis}${evidence}<p class="chat-boundary">证据边界：标题与摘要是来源内容的中文编译；比较、趋势和政策含义是基于当前站内样本的归纳。数字、承诺与立场请点击原文复核。</p>`);
  state.assistant.lastRecords = records;
  state.assistant.lastPlan = plan;
}

function setupAssistant() {
  $("chatForm").addEventListener("submit", event => {
    event.preventDefault();
    const input = $("chatInput");
    const query = input.value.trim();
    if (!query) return;
    input.value = "";
    answerQuestion(query);
  });
  document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => answerQuestion(button.dataset.prompt)));
}

function formatCount(value) {
  return new Intl.NumberFormat(state.language === "en" ? "en-GB" : "zh-CN").format(Number(value || 0));
}

function renderAnalytics() {
  const analytics = state.analytics;
  const container = $("analyticsKpis");
  if (!analytics || !analytics.records) {
    container.innerHTML = state.language === "en" ? '<div class="empty compact"><b>Corpus statistics are not available</b></div>' : '<div class="empty compact"><b>语料库统计暂未生成</b><p>下一次静态导出会自动写入 corpus_analytics.json。</p></div>';
    $("analyticsNote").textContent = state.language === "en" ? "No valid analytics file was found." : "未读取到可用统计文件。";
    return;
  }
  const taggedRate = `${Math.round((analytics.country_tagged_rate || 0) * 100)}%`;
  container.innerHTML = (state.language === "en" ? [
    ["Records", formatCount(analytics.records), `${analytics.date_start || "?"} to ${analytics.date_end || "?"}`],
    ["Days covered", formatCount(analytics.days_covered), `${analytics.avg_per_day || 0} records per day`],
    ["Topic tags", formatCount(analytics.topic_count), "Frequency and attention analysis"],
    ["Countries / regions", formatCount(analytics.country_count), `${taggedRate} explicitly geotagged`],
    ["Sources", formatCount(analytics.source_count), "Source concentration"],
  ] : [
    ["记录总量", formatCount(analytics.records), `${analytics.date_start || "?"} 至 ${analytics.date_end || "?"}`],
    ["覆盖天数", formatCount(analytics.days_covered), `日均 ${analytics.avg_per_day || 0} 条`],
    ["主题标签", formatCount(analytics.topic_count), "支持主题频率与热度分析"],
    ["国家/地区", formatCount(analytics.country_count), `明确地理标签覆盖 ${taggedRate}`],
    ["来源数量", formatCount(analytics.source_count), "用于评估来源集中度"],
  ]).map(([label, value, note]) => `<article class="analytics-kpi"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note)}</small></article>`).join("");
  renderLineChart("monthlyTrendChart", analytics.monthly_records || [], { x: "month", y: "count" });
  renderBarChart("topicBarChart", analytics.top_topics || [], { limit: 8, colorClass: "bar-fill" });
  renderBarChart("countryBarChart", analytics.top_countries || [], { limit: 10, colorClass: "bar-fill" });
  renderBarChart("continentBarChart", analytics.continents || [], { limit: 8, colorClass: "bar-fill alt" });
  renderBarChart("sourceBarChart", analytics.top_sources || [], { limit: 8, colorClass: "bar-fill alt" });
  renderHeatmap("countryTopicHeatmap", analytics.country_topic_matrix || {});
  $("analyticsNote").textContent = state.language === "en" ? "Descriptive statistics of the current archive; collection frequency is not a direct measure of real-world event frequency." : (analytics.notes || []).join(" ");
}

function openDialog(modal) {
  if (!modal) return;
  if (typeof modal.showModal === "function") {
    if (!modal.open) modal.showModal();
  } else {
    modal.setAttribute("open", "");
  }
}

function closeDialog(modal) {
  if (!modal) return;
  if (typeof modal.close === "function" && modal.open) modal.close();
  else modal.removeAttribute("open");
}

async function subscriptionConfig() {
  if (state.subscription) return state.subscription;
  state.subscription = await fetchJson("./data/subscription.json").catch(() => ({}));
  return state.subscription;
}

function subscriptionPayload(email) {
  return JSON.stringify({ email, list: "climate-weekly", source: location.href });
}

async function postSubscription(endpoint, email, timeoutMs = 30000) {
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    return await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: subscriptionPayload(email),
      cache: "no-store",
      credentials: "omit",
      keepalive: true,
      ...(controller ? { signal: controller.signal } : {}),
    });
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function queueSubscription(endpoint, email) {
  if (typeof navigator.sendBeacon !== "function") return false;
  const body = new Blob([subscriptionPayload(email)], { type: "text/plain;charset=UTF-8" });
  return navigator.sendBeacon(endpoint, body);
}

function setupSubscribe() {
  const openButtons = [...document.querySelectorAll("#subscribeOpen, [data-open-subscribe]")];
  const modal = $("subscribeModal");
  const form = $("subscribeForm");
  const close = $("subscribeClose");
  const unsubscribe = $("unsubscribeSubmit");
  if (!openButtons.length || !modal || !form || form.dataset.bound === "true") return;
  form.dataset.bound = "true";
  openButtons.forEach(button => button.addEventListener("click", () => {
    closeMobileMenu();
    openDialog(modal);
    setTimeout(() => $("subscribeEmail")?.focus(), 0);
  }));
  close?.addEventListener("click", () => closeDialog(modal));
  modal.addEventListener("click", event => {
    if (event.target === modal) closeDialog(modal);
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const submit = $("subscribeSubmit");
    const hint = $("subscribeHint");
    const fallback = $("subscribeFallback");
    const email = $("subscribeEmail").value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast("请输入有效邮箱。");
      return;
    }
    if (submit) { submit.disabled = true; submit.textContent = "提交中…"; }
    if (fallback) fallback.hidden = true;
    if (hint) hint.textContent = "正在连接订阅服务…";
    try {
      const config = await subscriptionConfig();
      if (!config.endpoint) throw new Error("订阅服务尚未配置");
      const response = await postSubscription(config.endpoint, email);
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      closeDialog(modal);
      toast("订阅成功，周报将在每周一发送。");
    } catch (error) {
      console.error("Subscribe endpoint failed", error);
      const config = await subscriptionConfig();
      if (config.endpoint && queueSubscription(config.endpoint, email)) {
        closeDialog(modal);
        toast("订阅请求已提交，使用同一邮箱重复提交不会重复订阅。");
      } else {
        if (hint) hint.textContent = "提交失败：当前网络无法连接订阅服务，请更换浏览器或网络后重试。";
        if (fallback) fallback.hidden = false;
      }
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = "提交订阅"; }
    }
  });
  unsubscribe?.addEventListener("click", async () => {
    const email = $("subscribeEmail").value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast("请先输入需要退订的有效邮箱。");
      return;
    }
    const endpoint = (await subscriptionConfig()).unsubscribe_endpoint;
    if (!endpoint) {
      toast("退订端点尚未配置，请通过联系邮箱申请退订。");
      return;
    }
    try {
      const response = await postSubscription(endpoint, email);
      if (!response.ok) throw new Error(String(response.status));
      closeDialog(modal);
      toast("退订成功，该邮箱将不再接收周报。");
    } catch (error) {
      console.error("Unsubscribe endpoint failed", error);
      toast("退订失败，请稍后重试或通过联系邮箱处理。");
    }
  });
}

function setupTeam() {
  const openButtons = [...document.querySelectorAll("#teamOpen, [data-open-team]")];
  const modal = $("teamModal");
  const close = $("teamClose");
  if (!openButtons.length || !modal) return;
  openButtons.forEach(button => button.addEventListener("click", () => {
    closeMobileMenu();
    const team = state.team || {};
    $("teamList").innerHTML = (team.members || []).map(member => `<article class="team-card">
      <h3>${esc(member.name)}</h3>
      <p>${esc(member.role)}</p>
      <a href="mailto:${esc(member.email)}">${esc(member.email)}</a>
      <small>${esc(member.research)}</small>
    </article>`).join("") || "暂无公开团队信息。";
    openDialog(modal);
  }));
  close?.addEventListener("click", () => closeDialog(modal));
}

function renderLineChart(id, rows, { x, y }) {
  const element = $(id);
  if (!element) return;
  if (!rows.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无趋势数据</b></div>';
    return;
  }
  const width = 920, height = 300, left = 54, right = 24, top = 20, bottom = 44;
  const values = rows.map(row => Number(row[y] || 0));
  const maxValue = Math.max(1, ...values);
  const span = Math.max(1, rows.length - 1);
  const px = index => left + index / span * (width - left - right);
  const py = value => top + (1 - value / maxValue) * (height - top - bottom);
  const points = rows.map((row, index) => [px(index), py(Number(row[y] || 0))]);
  const path = points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
  const area = `${path} L${points.at(-1)[0].toFixed(1)},${height - bottom} L${points[0][0].toFixed(1)},${height - bottom} Z`;
  const tickIndexes = [...new Set([0, Math.floor(span / 3), Math.floor(span * 2 / 3), span])];
  const grid = [0, .25, .5, .75, 1].map(ratio => {
    const yy = top + ratio * (height - top - bottom);
    const label = Math.round(maxValue * (1 - ratio));
    return `<line class="chart-gridline" x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}"></line><text class="chart-muted" x="${left - 8}" y="${yy + 4}" text-anchor="end">${label}</text>`;
  }).join("");
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="月度文本频率趋势图">
    ${grid}
    <path class="chart-area" d="${area}"></path>
    <path class="chart-line" d="${path}"></path>
    ${points.map((point, index) => index % Math.ceil(rows.length / 10) === 0 || index === rows.length - 1
      ? `<circle class="chart-dot" cx="${point[0]}" cy="${point[1]}" r="3.2"><title>${esc(rows[index][x])}: ${values[index]}</title></circle>`
      : "").join("")}
    <line class="chart-axis" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
    ${tickIndexes.map(index => `<text class="chart-muted" x="${px(index)}" y="${height - 15}" text-anchor="middle">${esc(rows[index][x])}</text>`).join("")}
  </svg>`;
}

function renderBarChart(id, rows, { limit = 8, colorClass = "bar-fill" } = {}) {
  const element = $(id);
  if (!element) return;
  const shown = rows.slice(0, limit);
  if (!shown.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无分布数据</b></div>';
    return;
  }
  const width = 520, rowHeight = 34, left = 120, right = 54, top = 12;
  const height = top * 2 + shown.length * rowHeight;
  const maxValue = Math.max(1, ...shown.map(row => Number(row.count || 0)));
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="分类频率条形图">
    ${shown.map((row, index) => {
      const y = top + index * rowHeight + 7;
      const barWidth = (width - left - right) * Number(row.count || 0) / maxValue;
      return `<text class="chart-label" x="${left - 10}" y="${y + 13}" text-anchor="end">${esc(row.name)}</text>
        <rect class="bar-track" x="${left}" y="${y}" width="${width - left - right}" height="16"></rect>
        <rect class="${colorClass}" x="${left}" y="${y}" width="${barWidth}" height="16"></rect>
        <text class="chart-value" x="${left + barWidth + 7}" y="${y + 12}">${formatCount(row.count)}</text>`;
    }).join("")}
  </svg>`;
}

function renderHeatmap(id, matrix) {
  const element = $(id);
  if (!element) return;
  const countries = matrix.countries || [];
  const topics = matrix.topics || [];
  const cells = matrix.cells || [];
  if (!countries.length || !topics.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无交叉矩阵</b></div>';
    return;
  }
  const maxValue = Math.max(1, ...cells.map(cell => Number(cell.count || 0)));
  const cellMap = new Map(cells.map(cell => [`${cell.country}||${cell.topic}`, Number(cell.count || 0)]));
  element.innerHTML = `<div class="heatmap" style="--heatmap-columns:${topics.length}">
    <div class="heatmap-row header"><span></span>${topics.map(topic => `<span>${esc(topic)}</span>`).join("")}</div>
    ${countries.map(country => `<div class="heatmap-row">
      <span class="heatmap-country">${esc(country)}</span>
      ${topics.map(topic => {
        const value = cellMap.get(`${country}||${topic}`) || 0;
        const alpha = 0.08 + 0.82 * value / maxValue;
        const ink = alpha > 0.46 ? "#fff" : "#12223a";
        return `<span class="heat-cell" style="background:rgba(23,78,166,${alpha.toFixed(3)});color:${ink}" title="${esc(country)} / ${esc(topic)}：${value}">${value || ""}</span>`;
      }).join("")}
    </div>`).join("")}
  </div>`;
}

async function init() {
  setupSubscribe();
  const [dashboard, archive, analytics, energyDashboard, energyArchive, energyAnalytics, siteMetrics, subscription, team, companyData, reportData, taxonomy, spotlights, carbonRegistry, topicDesks, transitionTracker] = await Promise.all([
    fetchJson("./data/dashboard.json"),
    fetchJson("./data/news_archive.json"),
    fetchJson("./data/corpus_analytics.json").catch(() => null),
    fetchJson("./data/energy_dashboard.json").catch(() => null),
    fetchJson("./data/energy_archive.json").catch(() => null),
    fetchJson("./data/energy_corpus_analytics.json").catch(() => null),
    fetchJson("./data/site_metrics.json").catch(() => null),
    fetchJson("./data/subscription.json").catch(() => null),
    fetchJson("./data/team.json").catch(() => null),
    fetchJson("./data/energy_companies.json").catch(() => null),
    fetchJson("./data/energy_reports.json").catch(() => null),
    fetchJson("./data/taxonomy.json").catch(() => ({ organization_groups: [], countries: [] })),
    fetchJson("./data/climate_spotlights.json").catch(() => null),
    fetchJson("./data/national_carbon_market_entities.json").catch(() => null),
    fetchJson("./data/topic_desks.json").catch(() => null),
    fetchJson("./data/energy_transition_tracker.json").catch(() => null),
  ]);
  state.siteMetrics = siteMetrics;
  state.subscription = subscription;
  state.team = team;
  state.companyData = companyData;
  state.reportData = reportData;
  state.taxonomy = taxonomy;
  state.spotlights = spotlights;
  state.carbonRegistry = carbonRegistry;
  state.topicDesks = topicDesks;
  state.transitionTracker = transitionTracker;
  state.datasets.climate = { dashboard, archive, analytics };
  if (energyDashboard && energyArchive) {
    state.datasets.energy = { dashboard: energyDashboard, archive: energyArchive, analytics: energyAnalytics };
  }
  const requestedMode = new URLSearchParams(location.search).get("mode") === "energy"
    || localStorage.getItem("climateTextMode") === "energy" ? "energy" : "climate";
  const requestedLanguage = new URLSearchParams(location.search).get("lang");
  state.language = requestedLanguage === "en" || (!requestedLanguage && localStorage.getItem("climateTextLanguage") === "en") ? "en" : "zh";
  setupCompanyIntelligence();
  setupCarbonRegistry();
  setupTaxonomyFilters();
  setupEnergyReports();
  setupMobileMenu();
  setupProjectIntro();
  activateMode(requestedMode);
  setupFilters();
  setupAssistant();
  setupTeam();
  renderSiteMetrics();
  setupMapPeriods();
  [$("modeToggle"), $("mobileModeToggle")].filter(Boolean).forEach(button => button.addEventListener("click", () => {
    closeMobileMenu();
    activateMode(state.mode === "energy" ? "climate" : "energy");
  }));
  [$("languageToggle"), $("mobileLanguageToggle")].filter(Boolean).forEach(button => button.addEventListener("click", () => {
    state.language = state.language === "en" ? "zh" : "en";
    localStorage.setItem("climateTextLanguage", state.language);
    closeMobileMenu();
    activateMode(state.mode);
  }));
  try {
    await switchMapPeriod("today");
  } catch (error) {
    console.error("Map rendering failed", error);
    $("mapLoading").innerHTML = '<b>地图底图暂未载入</b><span>仍可点击下方地点查看今日气候情报。</span>';
    $("mapCanvas").classList.add("map-error");
  }
}

init().catch(error => {
  console.error(error);
  toast("气候情报数据读取失败，请稍后刷新页面。");
});
