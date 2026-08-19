(() => {
  "use strict";

  const STORAGE = {
    themeOverride: "yoru.theme-override.v2",
    readingMode: "yoru.reading-mode.v1",
    progress: "yoru.progress.v1",
    readerWidth: "yoru.reader-width.v1",
  };
  const READER_WIDTHS = [720, 820, 920, 1040, 1160];
  const systemThemeQuery = window.matchMedia("(prefers-color-scheme: light)");
  const hostingConfig = window.YORU_CONFIG || {};

  const libraryPayload = window.MANGA_LIBRARY || { series: [] };
  let seriesList = Array.isArray(libraryPayload.series)
    ? libraryPayload.series
    : [];

  const elements = {
    body: document.body,
    brandButton: document.querySelector("#brand-button"),
    themeToggle: document.querySelector("#theme-toggle"),
    themeIcon: document.querySelector("#theme-icon"),
    readingModeToggle: document.querySelector("#reading-mode-toggle"),
    homeView: document.querySelector("#home-view"),
    readerView: document.querySelector("#reader-view"),
    seriesCount: document.querySelector("#series-count"),
    chapterCount: document.querySelector("#chapter-count"),
    pageCount: document.querySelector("#page-count"),
    refreshLibrary: document.querySelector("#refresh-library"),
    searchInput: document.querySelector("#search-input"),
    gallery: document.querySelector("#manga-gallery"),
    emptyState: document.querySelector("#empty-state"),
    readerBack: document.querySelector("#reader-back"),
    readerSeriesTitle: document.querySelector("#reader-series-title"),
    readerPageStatus: document.querySelector("#reader-page-status"),
    readerProgress: document.querySelector("#reader-progress"),
    readerPages: document.querySelector("#reader-pages"),
    chapterSelect: document.querySelector("#chapter-select"),
    previousChapter: document.querySelector("#previous-chapter"),
    nextChapter: document.querySelector("#next-chapter"),
    previousLabel: document.querySelector("#previous-label"),
    nextLabel: document.querySelector("#next-label"),
    readerWidthDown: document.querySelector("#reader-width-down"),
    readerWidthUp: document.querySelector("#reader-width-up"),
    readerWidthValue: document.querySelector("#reader-width-value"),
    toast: document.querySelector("#toast"),
  };

  const state = {
    currentSeries: null,
    currentChapterIndex: 0,
    currentPageIndex: 0,
    observer: null,
    readerWidthIndex: getStoredReaderWidthIndex(),
    toastTimer: null,
    refreshingLibrary: false,
  };

  function readStorage(key) {
    try {
      return localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_error) {
      // Preferences stay in memory when storage is disabled for file:// pages.
    }
  }

  function readJsonStorage(key, fallback) {
    try {
      const value = JSON.parse(readStorage(key));
      return value ?? fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function writeJsonStorage(key, value) {
    writeStorage(key, JSON.stringify(value));
  }

  function getProgressMap() {
    return readJsonStorage(STORAGE.progress, {});
  }

  function getStoredReaderWidthIndex() {
    const stored = Number.parseInt(readStorage(STORAGE.readerWidth), 10);
    if (Number.isInteger(stored) && stored >= 0 && stored < READER_WIDTHS.length) {
      return stored;
    }
    return 2;
  }

  function assetUrl(relativePath) {
    const encodedPath = String(relativePath)
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    const baseUrl = String(hostingConfig.assetBaseUrl || "../library/").replace(
      /\/?$/,
      "/",
    );
    return `${baseUrl}${encodedPath}`;
  }

  function loadStaticLibrary() {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `library-data.js?time=${Date.now()}`;
      script.onload = () => resolve(window.MANGA_LIBRARY || { series: [] });
      script.onerror = () => reject(new Error("Không thể tải library-data.js"));
      document.head.append(script);
    });
  }

  function replaceLibrary(runtimeLibrary) {
    seriesList = runtimeLibrary.series;
    updateStats();
    showHome();
  }

  function setRefreshState(isLoading) {
    state.refreshingLibrary = isLoading;
    elements.refreshLibrary.disabled = isLoading;
    elements.refreshLibrary.classList.toggle("is-loading", isLoading);
    elements.refreshLibrary.querySelector("span:last-child").textContent = isLoading
      ? "Đang quét…"
      : "Nạp lại";
  }

  async function refreshLibrary() {
    if (state.refreshingLibrary) return;
    setRefreshState(true);
    try {
      if (hostingConfig.staticLibrary) {
        const payload = await loadStaticLibrary();
        replaceLibrary({
          series: Array.isArray(payload.series) ? payload.series : [],
        });
        const chapterTotal = seriesList.reduce(
          (total, series) => total + series.chapters.length,
          0,
        );
        showToast(
          `Đã nạp ${seriesList.length} bộ truyện · ${chapterTotal} chapter`,
        );
        return;
      }
      if (window.location.protocol === "file:") {
        throw new Error(
          "Hãy mở bằng ‘Cập nhật thư viện.command’ để Yoru tự quét mà không hỏi folder.",
        );
      }
      const response = await fetch(`/api/library?time=${Date.now()}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Không thể quét thư viện (${response.status})`);
      const payload = await response.json();
      replaceLibrary({
        series: Array.isArray(payload.series) ? payload.series : [],
      });
      const chapterTotal = seriesList.reduce(
        (total, series) => total + series.chapters.length,
        0,
      );
      showToast(`Đã nạp ${seriesList.length} bộ truyện · ${chapterTotal} chapter`);
    } catch (error) {
      showToast(error?.message || "Không thể nạp lại thư viện");
    } finally {
      setRefreshState(false);
    }
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("vi-VN").format(value);
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add("is-visible");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      elements.toast.classList.remove("is-visible");
    }, 1800);
  }

  function systemTheme() {
    return systemThemeQuery.matches ? "light" : "dark";
  }

  function applyTheme(theme, isManualOverride = false) {
    const normalized = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = normalized;
    if (isManualOverride) {
      writeStorage(STORAGE.themeOverride, normalized);
    }
    const isDark = normalized === "dark";
    elements.themeIcon.textContent = isDark ? "☀" : "☾";
    const followingSystem = !readStorage(STORAGE.themeOverride);
    elements.themeToggle.setAttribute(
      "aria-label",
      isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối",
    );
    elements.themeToggle.title = followingSystem
      ? `Đang theo hệ thống (${isDark ? "dark" : "light"}). Click để chuyển thủ công.`
      : `Đang dùng ${isDark ? "dark" : "light"} theme thủ công.`;
  }

  function initializeTheme() {
    const storedOverride = readStorage(STORAGE.themeOverride);
    applyTheme(storedOverride || systemTheme());

    const readingMode = readStorage(STORAGE.readingMode) === "true";
    elements.body.classList.toggle("reading-soft", readingMode);
    elements.readingModeToggle.setAttribute("aria-pressed", String(readingMode));
  }

  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next, true);
    showToast(next === "dark" ? "Đã bật dark theme" : "Đã bật light theme");
  }

  function toggleReadingMode() {
    const enabled = !elements.body.classList.contains("reading-soft");
    elements.body.classList.toggle("reading-soft", enabled);
    elements.readingModeToggle.setAttribute("aria-pressed", String(enabled));
    writeStorage(STORAGE.readingMode, String(enabled));
    showToast(enabled ? "Đã bật chế độ dịu mắt" : "Đã tắt chế độ dịu mắt");
  }

  function updateStats() {
    const chapters = seriesList.reduce(
      (total, series) => total + series.chapters.length,
      0,
    );
    const pages = seriesList.reduce(
      (seriesTotal, series) =>
        seriesTotal +
        series.chapters.reduce(
          (chapterTotal, chapter) => chapterTotal + chapter.pages.length,
          0,
        ),
      0,
    );
    elements.seriesCount.textContent = formatNumber(seriesList.length);
    elements.chapterCount.textContent = formatNumber(chapters);
    elements.pageCount.textContent = formatNumber(pages);
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function openReaderRoute(seriesId, chapterIndex) {
    const hash = `#reader/${encodeURIComponent(seriesId)}/${chapterIndex}`;
    if (window.location.hash === hash) {
      routeFromHash();
    } else {
      window.location.hash = hash;
    }
  }

  function goHome() {
    if (window.location.hash === "#library") {
      showHome();
    } else {
      window.location.hash = "#library";
    }
  }

  function renderGallery(filterText = "") {
    const query = filterText.trim().toLocaleLowerCase("vi");
    const progressMap = getProgressMap();
    const filtered = seriesList.filter((series) =>
      `${series.title} ${series.displayTitle}`.toLocaleLowerCase("vi").includes(query),
    );

    elements.gallery.replaceChildren();
    elements.emptyState.hidden = filtered.length > 0;

    for (const series of filtered) {
      const article = createElement("article", "manga-card");
      const coverButton = createElement("button", "manga-card__cover");
      coverButton.type = "button";
      coverButton.setAttribute("aria-label", `Mở ${series.displayTitle}`);

      const cover = document.createElement("img");
      cover.src = assetUrl(series.cover);
      cover.alt = `Ảnh đại diện ${series.displayTitle}`;
      cover.loading = "lazy";
      cover.decoding = "async";
      const badge = createElement(
        "span",
        "manga-card__badge",
        series.chapters.length
          ? `${series.chapters.length} chapter`
          : "Chưa có chapter",
      );
      coverButton.append(cover, badge);

      const body = createElement("div", "manga-card__body");
      body.append(createElement("h3", "", series.displayTitle));
      const meta = createElement("div", "manga-card__meta");
      meta.append(
        createElement("span", "", series.years || "Trong thư viện"),
        createElement("span", "", `${formatNumber(series.pageCount)} trang`),
      );
      body.append(meta);

      const saved = progressMap[series.id];
      const defaultChapter = saved && series.chapters.length
        ? Math.min(saved.chapterIndex, series.chapters.length - 1)
        : 0;
      if (series.chapters.length) {
        coverButton.addEventListener("click", () => {
          openReaderRoute(series.id, defaultChapter);
        });
      } else {
        coverButton.disabled = true;
        coverButton.setAttribute("aria-label", `${series.displayTitle} chưa có chapter`);
      }

      if (saved && series.chapters.length) {
        const continueButton = createElement(
          "button",
          "manga-card__continue",
          `Đọc tiếp ${series.chapters[defaultChapter].label} →`,
        );
        continueButton.type = "button";
        continueButton.addEventListener("click", () => {
          openReaderRoute(series.id, defaultChapter);
        });
        body.append(continueButton);
      }

      article.append(coverButton, body);
      elements.gallery.append(article);
    }
  }

  function showHome() {
    disconnectPageObserver();
    state.currentSeries = null;
    elements.readerView.hidden = true;
    elements.homeView.hidden = false;
    elements.readerPages.replaceChildren();
    elements.readerProgress.style.width = "0%";
    document.title = "Yoru — Thư viện manga";
    renderGallery(elements.searchInput.value);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function saveReadingProgress(pageIndex) {
    if (!state.currentSeries) return;
    const progressMap = getProgressMap();
    progressMap[state.currentSeries.id] = {
      chapterIndex: state.currentChapterIndex,
      pageIndex,
      updatedAt: new Date().toISOString(),
    };
    writeJsonStorage(STORAGE.progress, progressMap);
  }

  function disconnectPageObserver() {
    if (state.observer) {
      state.observer.disconnect();
      state.observer = null;
    }
  }

  function updatePageStatus(pageIndex, pageTotal) {
    state.currentPageIndex = pageIndex;
    elements.readerPageStatus.textContent = `Trang ${pageIndex + 1} / ${pageTotal}`;
    elements.readerProgress.style.width = `${((pageIndex + 1) / pageTotal) * 100}%`;
    saveReadingProgress(pageIndex);
  }

  function observeReaderPages(pageTotal) {
    disconnectPageObserver();
    state.observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const pageIndex = Number.parseInt(visible.target.dataset.pageIndex, 10);
        updatePageStatus(pageIndex, pageTotal);
      },
      { rootMargin: "-24% 0px -48%", threshold: [0, 0.2, 0.55] },
    );
    elements.readerPages.querySelectorAll(".reader-page").forEach((page) => {
      state.observer.observe(page);
    });
  }

  function renderChapterSelect(series, activeIndex) {
    elements.chapterSelect.replaceChildren();
    series.chapters.forEach((chapter, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = chapter.label;
      option.selected = index === activeIndex;
      elements.chapterSelect.append(option);
    });
  }

  function updateChapterNavigation(series, activeIndex) {
    const previous = series.chapters[activeIndex - 1];
    const next = series.chapters[activeIndex + 1];
    elements.previousChapter.disabled = !previous;
    elements.nextChapter.disabled = !next;
    elements.previousLabel.textContent = previous ? previous.label : "Đầu truyện";
    elements.nextLabel.textContent = next ? next.label : "Cuối truyện";
  }

  function renderReader(series, chapterIndex) {
    const safeIndex = Math.max(0, Math.min(chapterIndex, series.chapters.length - 1));
    const chapter = series.chapters[safeIndex];
    const progressMap = getProgressMap();
    const saved = progressMap[series.id];
    const resumePage =
      saved && saved.chapterIndex === safeIndex
        ? Math.min(saved.pageIndex, chapter.pages.length - 1)
        : 0;

    state.currentSeries = series;
    state.currentChapterIndex = safeIndex;
    state.currentPageIndex = resumePage;

    elements.homeView.hidden = true;
    elements.readerView.hidden = false;
    elements.readerSeriesTitle.textContent = `${series.displayTitle} · ${chapter.label}`;
    elements.readerPageStatus.textContent = `Trang ${resumePage + 1} / ${chapter.pages.length}`;
    document.title = `${chapter.label} — ${series.displayTitle}`;

    renderChapterSelect(series, safeIndex);
    updateChapterNavigation(series, safeIndex);
    elements.readerPages.replaceChildren();

    let resumeAdjusted = false;
    chapter.pages.forEach((pagePath, pageIndex) => {
      const figure = createElement("figure", "reader-page");
      figure.dataset.pageIndex = String(pageIndex);
      const image = document.createElement("img");
      image.src = assetUrl(pagePath);
      image.alt = `${series.displayTitle}, ${chapter.label}, trang ${pageIndex + 1}`;
      image.decoding = "async";
      image.loading = pageIndex < 2 ? "eager" : "lazy";
      image.addEventListener("load", () => {
        const isLandscape = image.naturalWidth > image.naturalHeight;
        figure.classList.toggle("reader-page--landscape", isLandscape);
        figure.dataset.orientation = isLandscape ? "landscape" : "portrait";
        image.classList.add("is-loaded");
        if (pageIndex === resumePage && resumePage > 0 && !resumeAdjusted) {
          resumeAdjusted = true;
          figure.scrollIntoView({ block: "start", behavior: "auto" });
        }
      });
      image.addEventListener("error", () => {
        figure.dataset.error = "true";
        image.alt = `Không mở được trang ${pageIndex + 1}`;
      });
      figure.append(image);
      elements.readerPages.append(figure);
    });

    applyReaderWidth();
    observeReaderPages(chapter.pages.length);
    window.scrollTo({ top: 0, behavior: "auto" });
    if (resumePage > 0) {
      window.requestAnimationFrame(() => {
        elements.readerPages.children[resumePage]?.scrollIntoView({
          block: "start",
          behavior: "auto",
        });
      });
    }
  }

  function changeChapter(offset) {
    if (!state.currentSeries) return;
    const nextIndex = state.currentChapterIndex + offset;
    if (nextIndex < 0 || nextIndex >= state.currentSeries.chapters.length) return;
    openReaderRoute(state.currentSeries.id, nextIndex);
  }

  function applyReaderWidth() {
    const width = READER_WIDTHS[state.readerWidthIndex];
    document.documentElement.style.setProperty("--reader-width", `${width}px`);
    document.documentElement.style.setProperty(
      "--reader-landscape-width",
      `${width * 2}px`,
    );
    elements.readerWidthValue.textContent = `${width}px`;
    elements.readerWidthDown.disabled = state.readerWidthIndex === 0;
    elements.readerWidthUp.disabled = state.readerWidthIndex === READER_WIDTHS.length - 1;
    writeStorage(STORAGE.readerWidth, String(state.readerWidthIndex));
  }

  function changeReaderWidth(direction) {
    state.readerWidthIndex = Math.max(
      0,
      Math.min(READER_WIDTHS.length - 1, state.readerWidthIndex + direction),
    );
    applyReaderWidth();
  }

  function routeFromHash() {
    const match = window.location.hash.match(/^#reader\/([^/]+)\/(\d+)$/);
    if (!match) {
      showHome();
      return;
    }
    const seriesId = decodeURIComponent(match[1]);
    const chapterIndex = Number.parseInt(match[2], 10);
    const series = seriesList.find((item) => item.id === seriesId);
    if (!series || !series.chapters.length) {
      showToast("Không tìm thấy truyện hoặc chapter này");
      showHome();
      return;
    }
    renderReader(series, chapterIndex);
  }

  elements.themeToggle.addEventListener("click", toggleTheme);
  elements.readingModeToggle.addEventListener("click", toggleReadingMode);
  elements.brandButton.addEventListener("click", goHome);
  elements.readerBack.addEventListener("click", goHome);
  elements.searchInput.addEventListener("input", (event) => {
    renderGallery(event.target.value);
  });
  elements.refreshLibrary.addEventListener("click", refreshLibrary);
  elements.chapterSelect.addEventListener("change", (event) => {
    if (!state.currentSeries) return;
    openReaderRoute(state.currentSeries.id, Number.parseInt(event.target.value, 10));
  });
  elements.previousChapter.addEventListener("click", () => changeChapter(-1));
  elements.nextChapter.addEventListener("click", () => changeChapter(1));
  elements.readerWidthDown.addEventListener("click", () => changeReaderWidth(-1));
  elements.readerWidthUp.addEventListener("click", () => changeReaderWidth(1));
  const handleSystemThemeChange = () => {
    if (!readStorage(STORAGE.themeOverride)) {
      applyTheme(systemTheme());
    }
  };
  if (typeof systemThemeQuery.addEventListener === "function") {
    systemThemeQuery.addEventListener("change", handleSystemThemeChange);
  } else {
    systemThemeQuery.addListener(handleSystemThemeChange);
  }
  window.addEventListener("hashchange", routeFromHash);
  window.addEventListener("keydown", (event) => {
    const interactive = ["INPUT", "SELECT", "TEXTAREA"].includes(
      document.activeElement?.tagName,
    );
    if (interactive) return;
    if (event.key.toLocaleLowerCase() === "t") toggleTheme();
    if (event.key.toLocaleLowerCase() === "r") toggleReadingMode();
    if (!state.currentSeries) return;
    if (event.key === "Escape") goHome();
    if (event.key === "ArrowLeft") changeChapter(-1);
    if (event.key === "ArrowRight") changeChapter(1);
  });

  initializeTheme();
  updateStats();
  renderGallery();
  applyReaderWidth();
  routeFromHash();
})();
