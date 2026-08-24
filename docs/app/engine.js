
/* Health Condition Tracker Web - 分析引擎（移植自 scripts/analyze.py 等） */
window.HCT_ENGINE = (function () {
  var D = window.HCT_DATA;

  var ALIAS = {
    "拉肚子": "腹泻", "拉稀": "腹泻", "拉不出": "便秘", "便不出来": "便秘",
    "睡不着": "失眠", "睡不着觉": "失眠", "头昏": "头晕", "没力气": "乏力",
    "浑身无力": "乏力", "嗓子疼": "咽喉痛", "喉咙痛": "咽喉痛",
    "心口痛": "胸痛", "胸口痛": "胸痛", "胃痛": "腹痛", "肚子疼": "腹痛",
    "肚子痛": "腹痛", "胃胀气": "腹胀", "嗳气": "打嗝", "抽筋": "腿抽筋",
    "发冷": "怕冷", "出虚汗": "出汗过多", "口干舌燥": "口渴", "眼睛干": "眼干",
    "尿不出来": "排尿困难", "尿血": "血尿", "大便带血": "便血",
    "月经不来": "闭经", "月经量太大": "月经量多", "心闷": "胸闷",
    "喘不上气": "呼吸困难", "上不来气": "呼吸困难", "晕倒": "晕厥",
    "嘴歪": "口角歪斜", "说话不清": "言语不清", "手麻": "麻木", "脚麻": "麻木",
    "腿麻": "麻木", "心发慌": "心慌", "睡不好": "失眠",
    "发烧": "发热", "低烧": "发热", "高烧": "发热", "头疼": "头痛", "胃疼": "腹痛",
    "反胃": "恶心", "想吐": "恶心", "没胃口": "食欲不振", "吃不下饭": "食欲不振",
    "腰疼": "腰痛", "脖子疼": "颈痛", "脖子痛": "颈痛", "肩膀疼": "肩痛", "肩膀痛": "肩痛",
    "膝盖疼": "膝盖痛", "关节疼": "关节痛", "脚后跟疼": "足跟痛", "背疼": "背痛",
    "喘不过气": "呼吸困难", "憋气": "胸闷", "心口闷": "胸闷", "心跳快": "心悸",
    "身上没劲": "乏力", "没精神": "乏力", "出冷汗": "出汗过多", "夜间出汗": "盗汗",
    "月经不准": "月经不调", "月经推迟": "月经不调", "头晕眼花": "头晕", "头昏眼花": "头晕",
    "鼻子堵": "鼻塞", "鼻涕多": "流鼻涕", "眼干涩": "眼干", "喷嚏": "打喷嚏",
    "口气重": "口臭", "牙肉肿": "牙龈肿痛", "掉头发": "脱发", "皮肤痒": "皮肤瘙痒", "浑身痒": "皮肤瘙痒",
    "起疹子": "皮疹", "发麻": "麻木", "肚子胀": "腹胀", "胀气": "腹胀", "大便干": "便秘"
  };

  function norm(s) { return String(s == null ? '' : s).trim(); }

  function normalizeSymptoms(rawList) {
    var out = [];
    (rawList || []).forEach(function (s) {
      s = norm(s);
      if (!s) return;
      s = ALIAS[s] || s;
      if (out.indexOf(s) < 0) out.push(s);
    });
    return out;
  }

  function parseDate(v) {
    if (!v) return null;
    var s = norm(v).replace(/-/g, '/').replace(/T.*/, '');
    var m = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);
    if (!m) return null;
    var d = new Date(+m[1], +m[2] - 1, +m[3]);
    return isNaN(d.getTime()) ? null : d;
  }

  function todayISO() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function daysBetween(a, b) {
    var ms = (b.getTime() - a.getTime()) / 86400000;
    return Math.round(ms);
  }

  function parseDuration(value) {
    if (value === null || value === undefined) return null;
    var s = norm(value).toLowerCase();
    if (!s) return null;
    var units = [["年", 365], ["岁", 365], ["月", 30], ["周", 7], ["星期", 7], ["天", 1], ["日", 1], ["d", 1]];
    for (var i = 0; i < units.length; i++) {
      if (s.indexOf(units[i][0]) >= 0) {
        var m = s.match(/(\d+(?:\.\d+)?)/);
        if (m) return Math.round(parseFloat(m[1]) * units[i][1]);
      }
    }
    var n = parseFloat(s);
    return isNaN(n) ? null : Math.round(n);
  }

  function extractSymptomsFromRecord(rec) {
    var list = [];
    if (rec && Array.isArray(rec.symptoms) && rec.symptoms.length) {
      rec.symptoms.forEach(function (x) { if (x && x.name && list.indexOf(norm(x.name)) < 0) list.push(norm(x.name)); });
      return list;
    }
    if (rec && rec.symptom) list.push(norm(rec.symptom));
    return list;
  }

  function historyStats(logs, days) {
    var counts = {}, recent7 = {};
    var now = new Date();
    var cutoff = days ? new Date(now.getTime() - days * 86400000) : null;
    var sevenAgo = new Date(now.getTime() - 7 * 86400000);
    (logs || []).forEach(function (rec) {
      var d = parseDate(rec && rec.date);
      if (cutoff && (!d || d < cutoff)) return;
      extractSymptomsFromRecord(rec).forEach(function (name) {
        if (!name) return;
        counts[name] = (counts[name] || 0) + 1;
        if (d && d >= sevenAgo) recent7[name] = (recent7[name] || 0) + 1;
      });
    });
    return { counts: counts, recent7: recent7 };
  }

  function diseaseSpecificity(disease, mapData) {
    var total = 0;
    Object.keys(mapData).forEach(function (k) {
      if (mapData[k].indexOf(disease) >= 0) total++;
    });
    return 1 / (1 + total);
  }

  function detectCourse(symptoms, counts, recent7, durationDays, trend) {
    var total = symptoms.length ? symptoms.reduce(function (a, s) { return a + (counts[s] || 0); }, 0)
                                : Object.keys(counts).reduce(function (a, k) { return a + counts[k]; }, 0);
    var r7 = symptoms.length ? symptoms.reduce(function (a, s) { return a + (recent7[s] || 0); }, 0)
                             : Object.keys(recent7).reduce(function (a, k) { return a + recent7[k]; }, 0);
    var kind;
    if (trend === "快速恶化" || trend === "明显加重" || trend === "加重") kind = "加重中";
    else if (trend === "好转") kind = "好转中";
    else if (durationDays !== null && durationDays !== undefined) {
      if (durationDays <= 14) kind = "新发（≤2周）";
      else if (durationDays <= 30) kind = "亚急性（2周-1个月）";
      else kind = "慢性（>1个月）";
    } else if (total >= 3 && r7 > 0) kind = "反复发作";
    else if (total === 0) kind = "新发（首次记录）";
    else kind = "情况待补充（可提供病程时长）";
    var worsening = (trend === "快速恶化" || trend === "明显加重" || trend === "加重") || (total >= 2 && r7 >= 1 && r7 / total >= 0.5);
    var stable = kind.indexOf("慢性") === 0 && !worsening;
    return { kind: kind, days: durationDays, worsening: worsening, stable: stable };
  }

  function _hit(disease, riskMap) {
    for (var k in riskMap) {
      if (k === disease || k.indexOf(disease) >= 0 || disease.indexOf(k) >= 0) return k;
    }
    return null;
  }

  function assessRisk(symptoms, scored, severity, quiz, course, overdue, trend) {
    var rf = D.red_flags || {};
    var urgentFlags = rf["紧急症状"] || [];
    var watchFlags = rf["警惕症状"] || [];
    var emergencyMap = (D.disease_risk || {})["紧急"] || {};
    var midMap = (D.disease_risk || {})["中危"] || {};
    var sev = null;
    if (severity !== null && severity !== undefined && severity !== '') {
      var n = parseInt(severity, 10);
      if (!isNaN(n)) sev = n;
    }
    var reasons = [], urgentHits = [], watchHits = [];

    (symptoms || []).forEach(function (s) {
      if (urgentFlags.indexOf(s) >= 0) { urgentHits.push(s); reasons.push('症状「' + s + '」属于需要立即评估的情况'); }
      else if (watchFlags.indexOf(s) >= 0) { watchHits.push(s); reasons.push('症状「' + s + '」需结合程度判断'); }
    });

    (scored || []).forEach(function (item) {
      var d = item.disease;
      var k = _hit(d, emergencyMap);
      if (k) {
        if ((item.input.length >= 2 && sev !== null && sev >= 6) || (sev !== null && sev >= 8) ||
            item.input.some(function (s) { return urgentFlags.indexOf(s) >= 0; })) {
          urgentHits.push(k); reasons.push('「' + k + '」与急症疾病相关，且符合就医指征');
        } else {
          watchHits.push(k); reasons.push('「' + k + '」需排查（急症相关，但暂不构成紧急）');
        }
      } else {
        var k2 = _hit(d, midMap);
        if (k2) { watchHits.push(k2); reasons.push('「' + k2 + '」需排查'); }
      }
    });

    if (sev !== null) {
      if (sev >= 9) { urgentHits.push('严重程度达到 9-10'); reasons.push('严重程度 9-10（无法忍受）'); }
      else if (sev >= 7) { watchHits.push('严重程度达到 7-8'); reasons.push('严重程度 7-8（较明显）'); }
    }

    if (quiz && typeof quiz === 'object') {
      if (quiz.red_flag) { urgentHits.push('客观评估命中紧急警示'); reasons.push('客观评估命中紧急警示：「' + (quiz.red_flag_hit || '是') + '」'); }
      var trendObj = (quiz.dimensions || {})['时间趋势'] || {};
      if (trendObj.label === '快速恶化') { watchHits.push('快速恶化'); reasons.push('客观评估提示快速恶化'); }
      var qscore = (quiz.score !== null && quiz.score !== undefined) ? parseFloat(quiz.score) : null;
      if (!isNaN(qscore)) {
        if (qscore >= 9) { urgentHits.push('客观评估综合分≥9'); reasons.push('客观评估综合分 ' + qscore + '/10'); }
        else if (qscore >= 7) { watchHits.push('客观评估综合分≥7'); reasons.push('客观评估综合分 ' + qscore + '/10'); }
      }
    }

    var level, action;
    if (urgentHits.length || (sev !== null && sev >= 9)) {
      level = "紧急"; action = "建议立即就医（必要时拨打 120），不要拖延。";
    } else if (watchHits.length && ((sev !== null && sev >= 7) || watchHits.indexOf("快速恶化") >= 0)) {
      level = "中危"; action = "建议尽快（1-2 天内）就诊，避免拖延。";
    } else if (sev !== null && sev >= 7) {
      level = "中危"; action = "程度较明显（7-8 分），建议尽快（1-2 天内）就诊，避免拖延。";
    } else if (watchHits.length && sev !== null && sev >= 4) {
      level = "中"; action = "建议近期（1-7 天）安排门诊检查；症状持续或加重时提前就诊。";
    } else if (watchHits.length && sev === null) {
      level = "中"; action = "未提供严重程度；建议近期安排门诊评估，若出现升级条件请提前。";
    } else {
      level = "低"; action = "程度较轻，符合多数常见情况（如吃坏肚子、受凉、疲劳），建议先休息观察 1-3 天；持续不缓解或加重再就诊。";
    }

    if (level === "低" && overdue && overdue.length && trend !== "好转" && !(course || {}).stable) {
      level = "中"; action = "症状持续时间已超过建议就诊时长（Mayo/NHS），建议安排门诊检查。";
      reasons.push('「' + overdue.slice(0, 3).join('、') + '」持续时间超过国际指南建议就诊时长');
    }

    var extra = [];
    (scored || []).forEach(function (item) {
      var d = item.disease;
      var k = _hit(d, emergencyMap);
      if (k) extra.push(k + '：' + emergencyMap[k]);
      else { var k2 = _hit(d, midMap); if (k2) extra.push(k2 + '：' + midMap[k2]); }
    });

    course = course || {};
    if (level !== "紧急") {
      if (course.stable) {
        if (level === "中危") { level = "中"; action = "病程慢性稳定，建议近期复查即可；症状有变化时再提前就诊。"; }
        else if (level === "中") { level = "低"; action = "病程偏慢性且稳定，按原计划复诊即可；症状有变化时再提前就诊。"; }
        reasons.push("病程慢性稳定，已按长期客观情况降低紧急度");
      } else if (course.worsening) {
        if (level === "低") { level = "中"; action = "近期有加重趋势，建议近期安排门诊检查。"; }
        else if (level === "中") { level = "中危"; action = "近期呈加重趋势，建议尽快（1-2 天内）就诊。"; }
        reasons.push("近期呈加重趋势，已适当升级关注");
      } else if (course.kind && course.kind.indexOf("新发") === 0 && sev !== null && sev >= 8 && level === "中") {
        level = "中危"; action = "新发且程度较重，建议尽快（1-2 天内）就诊。"; reasons.push("新发且程度较重");
      }
    }

    return {
      level: level, action: action, reasons: reasons.slice(0, 8),
      advice: extra.slice(0, 4),
      calm: "风险分级是保守筛查，用于提醒就医时机，不构成诊断；大多数症状为常见病，不必过度紧张。",
      course: course
    };
  }

  function analyze(opts) {
    opts = opts || {};
    var rawSyms = normalizeSymptoms(opts.symptoms);
    var hist = historyStats(opts.logs || [], opts.days || 0);
    var allSyms = rawSyms.slice();
    Object.keys(hist.counts).forEach(function (s) { if (allSyms.indexOf(s) < 0) allSyms.push(s); });
    var mapData = D.symptom_disease_map || {};
    var diseaseMatches = {};
    function addMatch(disease, sym) {
      if (!diseaseMatches[disease]) diseaseMatches[disease] = [];
      if (diseaseMatches[disease].indexOf(sym) < 0) diseaseMatches[disease].push(sym);
    }
    allSyms.forEach(function (sym) {
      (mapData[sym] || []).forEach(function (d) { addMatch(d, sym); });
    });
    var rf = D.red_flags || {};
    var urgentFlags = rf["紧急症状"] || [];
    var scored = [];
    Object.keys(diseaseMatches).forEach(function (d) {
      var matched = diseaseMatches[d];
      var matchedInput = matched.filter(function (s) { return rawSyms.indexOf(s) >= 0; });
      var matchedHist = matched.filter(function (s) { return rawSyms.indexOf(s) < 0; });
      var spec = diseaseSpecificity(d, mapData);
      var score = matchedInput.length * 100 + matchedHist.length * 20 + spec * 10;
      if (matchedInput.some(function (s) { return urgentFlags.indexOf(s) >= 0; })) score += 30;
      var confidence = "高";
      if (matchedInput.length === 1) confidence = (spec >= 0.2) ? "中" : "低";
      else if (matchedInput.length === 0) confidence = "低";
      scored.push({ disease: d, score: score, input: matchedInput.slice().sort(), history: matchedHist.slice().sort(), specificity: Math.round(spec * 1000) / 1000, confidence: confidence });
    });
    scored.sort(function (a, b) { return b.score - a.score || b.specificity - a.specificity; });

    var tiers = { "高度相关": [], "可能相关": [], "需注意（仅历史）": [] };
    scored.forEach(function (item) {
      if (item.input.length >= 2) tiers["高度相关"].push(item);
      else if (item.input.length === 1) tiers["可能相关"].push(item);
      else tiers["需注意（仅历史）"].push(item);
    });

    var departments = {};
    var deptMap = D.department_map || {};
    allSyms.forEach(function (sym) {
      (deptMap[sym] || []).forEach(function (d) { departments[d] = (departments[d] || 0) + 1; });
    });

    var durationDays = opts.durationText ? parseDuration(opts.durationText) : null;
    var course = detectCourse(allSyms, hist.counts, hist.recent7, durationDays, opts.trend || "");
    var overdue = [];
    if (durationDays) {
      var careSyms = (D.care_pathways || {}).symptoms || {};
      allSyms.forEach(function (sym) {
        var thr = (careSyms[sym] || {}).appointment_after_days;
        if (thr && durationDays >= thr && opts.trend !== "好转") overdue.push(sym);
      });
    }
    var risk = assessRisk(allSyms, scored, opts.severity, opts.quiz, course, overdue, opts.trend || "");
    return {
      symptoms: allSyms, history: hist.counts, recent7: hist.recent7, course: course,
      tiers: tiers, departments: departments, risk: risk, quiz: opts.quiz, overdue: overdue
    };
  }

  var LEVEL_TO_PATHWAY = { "紧急": "急诊", "中危": "尽快", "中": "近期", "低": "家庭观察" };

  function carePathway(result) {
    var care = D.care_pathways || {};
    var levels = {};
    (care.levels || []).forEach(function (x) { levels[x.level] = x; });
    var risk = result.risk || {};
    var level = risk.level || "低";
    var pkey = LEVEL_TO_PATHWAY[level] || "家庭观察";
    var course = result.course || {};
    if (level === "低" && course.stable) pkey = "门诊";
    var plv = levels[pkey] || levels["家庭观察"] || {};
    var out = {
      key: pkey, label: plv.label || pkey, timeframe: plv.timeframe || "", advice: plv.advice || "",
      symptoms: [], sources: care.sources || []
    };
    var shown = 0;
    (result.symptoms || []).slice(0, 2).forEach(function (sym) {
      var careSyms = care.symptoms || {};
      var guidance = careSyms[sym] || careSyms["default"] || {};
      if (!guidance || !Object.keys(guidance).length) return;
      var tierOrder = ["家庭观察", "门诊", "近期", "尽快", "急诊"];
      var cur = pkey;
      var curDisplay = cur;
      if (!guidance[cur]) {
        var idx0 = tierOrder.indexOf(cur);
        for (var i = idx0 - 1; i >= 0; i--) {
          if (guidance[tierOrder[i]]) { curDisplay = tierOrder[i]; break; }
        }
      }
      var item = { symptom: sym, current: null, upgrade: null };
      if (guidance[curDisplay]) item.current = { tier: curDisplay, text: guidance[curDisplay] };
      var idx = tierOrder.indexOf(curDisplay);
      for (var j = idx + 1; j < tierOrder.length; j++) {
        if (guidance[tierOrder[j]]) { item.upgrade = { tier: tierOrder[j], text: guidance[tierOrder[j]] }; break; }
      }
      out.symptoms.push(item);
      shown++;
      if (shown >= 2) return;
    });
    return out;
  }

  function recommendDepartments(symptoms) {
    var deptMap = D.department_map || {};
    var counts = {};
    (symptoms || []).forEach(function (sym) {
      (deptMap[sym] || []).forEach(function (d) { counts[d] = (counts[d] || 0) + 1; });
    });
    return Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).map(function (d) { return { name: d, count: counts[d] }; });
  }

  function normCity(c) {
    c = norm(c);
    if (!c) return "";
    return c.replace(/市$/, "");
  }

  var CITY_PROVINCE = {
    "北京":"北京","上海":"上海","天津":"天津","重庆":"重庆",
    "广州":"广东","深圳":"广东","东莞":"广东","佛山":"广东","珠海":"广东","中山":"广东","惠州":"广东","汕头":"广东",
    "杭州":"浙江","宁波":"浙江","温州":"浙江","绍兴":"浙江","嘉兴":"浙江","台州":"浙江","金华":"浙江","湖州":"浙江",
    "南京":"江苏","苏州":"江苏","无锡":"江苏","常州":"江苏","南通":"江苏","徐州":"江苏","扬州":"江苏","盐城":"江苏","淮安":"江苏","连云港":"江苏",
    "济南":"山东","青岛":"山东","烟台":"山东","潍坊":"山东","淄博":"山东","临沂":"山东","济宁":"山东","泰安":"山东",
    "郑州":"河南","洛阳":"河南","南阳":"河南","新乡":"河南","开封":"河南","许昌":"河南",
    "武汉":"湖北","襄阳":"湖北","宜昌":"湖北","荆州":"湖北","黄冈":"湖北",
    "长沙":"湖南","株洲":"湖南","湘潭":"湖南","岳阳":"湖南","常德":"湖南","衡阳":"湖南","郴州":"湖南","永州":"湖南",
    "成都":"四川","绵阳":"四川","南充":"四川","泸州":"四川","宜宾":"四川","乐山":"四川","德阳":"四川","达州":"四川",
    "西安":"陕西","咸阳":"陕西","宝鸡":"陕西","渭南":"陕西","榆林":"陕西","汉中":"陕西",
    "沈阳":"辽宁","大连":"辽宁","鞍山":"辽宁","抚顺":"辽宁",
    "长春":"吉林","吉林":"吉林","四平":"吉林","延吉":"吉林",
    "哈尔滨":"黑龙江","齐齐哈尔":"黑龙江","大庆":"黑龙江","牡丹江":"黑龙江",
    "石家庄":"河北","唐山":"河北","保定":"河北","邯郸":"河北","廊坊":"河北","秦皇岛":"河北",
    "太原":"山西","大同":"山西","临汾":"山西","运城":"山西",
    "合肥":"安徽","芜湖":"安徽","蚌埠":"安徽","安庆":"安徽","阜阳":"安徽","滁州":"安徽",
    "福州":"福建","厦门":"福建","泉州":"福建","漳州":"福建","莆田":"福建","宁德":"福建",
    "南昌":"江西","赣州":"江西","九江":"江西","上饶":"江西","宜春":"江西",
    "昆明":"云南","曲靖":"云南","大理":"云南","丽江":"云南","玉溪":"云南",
    "贵阳":"贵州","遵义":"贵州","六盘水":"贵州","毕节":"贵州",
    "南宁":"广西","柳州":"广西","桂林":"广西","梧州":"广西","北海":"广西",
    "海口":"海南","三亚":"海南","儋州":"海南",
    "兰州":"甘肃","天水":"甘肃","酒泉":"甘肃",
    "西宁":"青海","格尔木":"青海",
    "银川":"宁夏","石嘴山":"宁夏",
    "乌鲁木齐":"新疆","喀什":"新疆","伊犁":"新疆",
    "呼和浩特":"内蒙古","包头":"内蒙古","鄂尔多斯":"内蒙古","赤峰":"内蒙古",
    "拉萨":"西藏","日喀则":"西藏",
    "香港":"香港","澳门":"澳门","台北":"台湾"
  };

  function resolveProvince(city, province) {
    if (norm(province)) return norm(province);
    if (city && CITY_PROVINCE[city]) return CITY_PROVINCE[city];
    return "";
  }

  function splitByLocation(hospitals, city, province) {
    var sameCity = [], sameProv = [], others = [];
    (hospitals || []).forEach(function (h) {
      var hCity = normCity(h.city || "");
      var hProv = norm(h.province || "");
      if (city && hCity === city) sameCity.push(h);
      else if (province && hProv === province) sameProv.push(h);
      else others.push(h);
    });
    return { sameCity: sameCity, sameProv: sameProv, others: others };
  }

  function hospitalAdvice(departments, city, province) {
    var specs = (D.hospitals || {}).specialties || {};
    var feeNote = (D.hospitals || {})["费用提示"] || "";
    city = normCity(city);
    province = resolveProvince(city, province);
    var out = { city: city, province: province, departments: (departments || []).slice(0, 3), groups: [], plan: { anyCity: false, anyProv: false } };
    var anyCity = false, anyProv = false;
    (departments || []).slice(0, 3).forEach(function (dep) {
      var hospitals = specs[dep] || [];
      if (!hospitals.length) { out.groups.push({ department: dep, empty: true }); return; }
      var split = splitByLocation(hospitals, city, province);
      if (split.sameCity.length) anyCity = true;
      if (split.sameProv.length) anyProv = true;
      out.groups.push({ department: dep, sameCity: split.sameCity, sameProv: split.sameProv.slice(0, 3), others: split.others.slice(0, 5) });
    });
    out.plan.anyCity = anyCity;
    out.plan.anyProv = anyProv;
    out.plan.feeNote = feeNote;
    return out;
  }

  function severityScore(answers, mode) {
    var dims = (D.severity_scale || {}).dimensions || {};
    var score = null, redFlag = false, redFlagHit = "";
    var redFlags = (D.severity_scale || {}).red_flags || [];
    var dimsOut = {};
    var collected = [];
    Object.keys(dims).forEach(function (key) {
      var d = dims[key];
      if (!answers || answers[key] === undefined || answers[key] === null || answers[key] === '') return;
      var val = answers[key];
      var sub = { key: key, question: d.question, weight: d.weight, label: '', raw: val };
      if (d.type === '0-10') {
        var n = parseFloat(val);
        if (isNaN(n)) return;
        sub.value = n / 10; // 0-1
        sub.label = n + '/10';
        if (key === '疼痛不适强度' && n >= 9) { redFlag = true; redFlagHit = '疼痛不适强度 ≥9'; }
      } else {
        var opts = d.options || {};
        var v = opts[val];
        if (v === undefined) return;
        sub.value = v / 3; // 0-1
        sub.label = val;
        if (key === '时间趋势' && val === '快速恶化') { redFlag = true; redFlagHit = '时间趋势：快速恶化'; }
      }
      dimsOut[key] = { label: sub.label, value: sub.value, raw: sub.raw };
      collected.push(sub);
    });
    var isQuick = (mode === 'quick');
    if (isQuick) {
      // 快速版：强度 + 睡眠 + 工作/学习影响 三题，其余用默认 0
      var totalW = 0, sum = 0;
      ['疼痛不适强度', '睡眠影响', '工作学习影响'].forEach(function (k) {
        var d = dims[k]; if (!d) return;
        var v = (answers && answers[k] !== undefined && answers[k] !== null && answers[k] !== '') ? (dimsOut[k] ? dimsOut[k].value : 0) : 0;
        sum += v * d.weight; totalW += d.weight;
      });
      if (totalW > 0) score = Math.min(10, Math.round((sum / totalW) * 10 * 10) / 10);
    } else {
      if (collected.length) {
        var wsum = 0, ssum = 0;
        collected.forEach(function (c) { ssum += c.value * c.weight; wsum += c.weight; });
        if (wsum > 0) score = Math.min(10, Math.round((ssum / wsum) * 10 * 10) / 10);
      }
    }
    return { score: score, red_flag: redFlag, red_flag_hit: redFlagHit, dimensions: dimsOut };
  }

  function collectReminders(medications, treatments, days) {
    days = days || 7;
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var out = [];
    (treatments || []).forEach(function (p) {
      if (p.status === "已执行") return;
      var d = parseDate(p.follow_up_date);
      if (!d) return;
      var left = daysBetween(today, d);
      if (left <= days) out.push({ kind: "复诊", member: p.member || "", title: p.diagnosis || "", date: d, left: left });
    });
    (medications || []).forEach(function (m) {
      var d = parseDate(m.end_date);
      if (!d) return;
      var left = daysBetween(today, d);
      if (left >= 0 && left <= days) out.push({ kind: "停药", member: m.member || "", title: m.name || "", date: d, left: left });
    });
    out.sort(function (a, b) { return a.date - b.date; });
    return out;
  }

  function matchSymptoms(text) {
    var t = norm(text);
    var found = [];
    if (!t) return found;
    var known = Object.keys(D.symptom_disease_map || {});
    known.forEach(function (s) { if (t.indexOf(s) >= 0 && found.indexOf(s) < 0) found.push(s); });
    var aliases = Object.keys(ALIAS);
    aliases.forEach(function (a) { if (t.indexOf(a) >= 0) { var s = ALIAS[a]; if (found.indexOf(s) < 0) found.push(s); } });
    return found;
  }

  return {
    ALIAS: ALIAS, normalizeSymptoms: normalizeSymptoms, parseDuration: parseDuration,
    parseDate: parseDate, todayISO: todayISO, daysBetween: daysBetween,
    historyStats: historyStats, analyze: analyze, carePathway: carePathway,
    recommendDepartments: recommendDepartments, hospitalAdvice: hospitalAdvice,
    severityScore: severityScore, collectReminders: collectReminders,
    matchSymptoms: matchSymptoms, normCity: normCity, resolveProvince: resolveProvince
  };
})();
