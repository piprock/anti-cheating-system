/**
 * Avatar AI Accessibility & Theme Manager
 * Керує:
 * - Світлою / Нічною темами
 * - Масштабуванням контенту для людей з порушенням зору (A / A+ / A++)
 * - Режимами для дальтоніків (Протанопія, Дейтеранопія, Тританопія, Високий контраст)
 * - Збереженням у localStorage та миттєвим застосуванням без перезавантаження
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'avatarai_a11y_settings';
  const LEGACY_STORAGE_KEY = 'teachai_a11y_settings';

  const DEFAULT_SETTINGS = {
    theme: 'dark',
    fontScale: 'normal',
    colorblind: 'none'
  };

  /**
   * SVG-шаблони іконок сонця та місяця
   */
  const SUN_ICON_SVG = '<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';

  const MOON_ICON_SVG = '<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';

  /**
   * Отримати збережені або стандартні налаштування
   */
  function getSettings() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
      if (saved) {
        return Object.assign({}, DEFAULT_SETTINGS, JSON.parse(saved));
      }
    } catch (e) {
      console.warn('Could not read a11y settings from localStorage', e);
    }
    return Object.assign({}, DEFAULT_SETTINGS);
  }

  /**
   * Зберегти налаштування в localStorage
   */
  function saveSettings(settings) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.warn('Could not save a11y settings', e);
    }
  }

  /**
   * Застосувати налаштування до document.documentElement
   */
  function applySettings(settings) {
    const root = document.documentElement;

    // 1. Тема
    root.setAttribute('data-theme', settings.theme);

    // 2. Масштаб шрифту
    root.setAttribute('data-font-scale', settings.fontScale);

    // 3. Режим дальтоніка
    root.setAttribute('data-colorblind', settings.colorblind);

    // Оновити кнопку швидкого перемикання теми
    updateQuickThemeBtn(settings.theme);

    // Оновити стани активності всередині модалки
    updateModalUI(settings);
  }

  /**
   * Оновити іконку та aria-label на кнопці швидкого перемикання теми
   */
  function updateQuickThemeBtn(theme) {
    const iconEl = document.getElementById('themeQuickIcon');
    const btnEl = document.getElementById('themeQuickBtn');
    if (!iconEl || !btnEl) return;

    if (theme === 'dark') {
      iconEl.innerHTML = SUN_ICON_SVG;
      btnEl.setAttribute('aria-label', 'Перемкнути на світлу тему');
      btnEl.setAttribute('title', 'Увімкнути світлу тему');
    } else {
      iconEl.innerHTML = MOON_ICON_SVG;
      btnEl.setAttribute('aria-label', 'Перемкнути на нічну тему');
      btnEl.setAttribute('title', 'Увімкнути нічну тему');
    }
  }

  /**
   * Оновити активні класи кнопок у модальному вікні
   */
  function updateModalUI(settings) {
    // Тема
    document.querySelectorAll('[data-theme-choice]').forEach((btn) => {
      const val = btn.getAttribute('data-theme-choice');
      btn.classList.toggle('active', val === settings.theme);
    });

    // Масштаб
    document.querySelectorAll('[data-scale-choice]').forEach((btn) => {
      const val = btn.getAttribute('data-scale-choice');
      btn.classList.toggle('active', val === settings.fontScale);
    });

    // Дальтонізм
    document.querySelectorAll('[data-colorblind-choice]').forEach((card) => {
      const val = card.getAttribute('data-colorblind-choice');
      const radio = card.querySelector('input[type="radio"]');
      const isActive = val === settings.colorblind;
      card.classList.toggle('active', isActive);
      if (radio) radio.checked = isActive;
    });
  }

  /**
   * Ініціалізація слухачів подій після завантаження DOM
   */
  function initA11yListeners() {
    let currentSettings = getSettings();
    applySettings(currentSettings);

    const backdrop = document.getElementById('a11yBackdrop');
    const openBtn = document.getElementById('a11yOpenBtn');
    const closeBtn = document.getElementById('a11yCloseBtn');
    const doneBtn = document.getElementById('a11yDoneBtn');
    const resetBtn = document.getElementById('a11yResetBtn');
    const quickThemeBtn = document.getElementById('themeQuickBtn');

    function openModal() {
      if (backdrop) {
        backdrop.classList.add('active');
        backdrop.removeAttribute('hidden');
        if (closeBtn) closeBtn.focus();
      }
    }

    function closeModal() {
      if (backdrop) {
        backdrop.classList.remove('active');
        backdrop.setAttribute('hidden', '');
        if (openBtn) openBtn.focus();
      }
    }

    if (openBtn) openBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (doneBtn) doneBtn.addEventListener('click', closeModal);

    // Закриття по кліку на бекдроп поза модалкою
    if (backdrop) {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeModal();
      });
    }

    // Закриття клавішею Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && backdrop && backdrop.classList.contains('active')) {
        closeModal();
      }
    });

    // Швидка зміна теми
    if (quickThemeBtn) {
      quickThemeBtn.addEventListener('click', () => {
        currentSettings = getSettings();
        currentSettings.theme = currentSettings.theme === 'dark' ? 'light' : 'dark';
        saveSettings(currentSettings);
        applySettings(currentSettings);
      });
    }

    // Вибір теми в модалці
    document.querySelectorAll('[data-theme-choice]').forEach((btn) => {
      btn.addEventListener('click', () => {
        currentSettings.theme = btn.getAttribute('data-theme-choice');
        saveSettings(currentSettings);
        applySettings(currentSettings);
      });
    });

    // Вибір масштабу в модалці
    document.querySelectorAll('[data-scale-choice]').forEach((btn) => {
      btn.addEventListener('click', () => {
        currentSettings.fontScale = btn.getAttribute('data-scale-choice');
        saveSettings(currentSettings);
        applySettings(currentSettings);
      });
    });

    // Вибір режиму дальтоніка
    document.querySelectorAll('[data-colorblind-choice]').forEach((card) => {
      card.addEventListener('click', () => {
        currentSettings.colorblind = card.getAttribute('data-colorblind-choice');
        saveSettings(currentSettings);
        applySettings(currentSettings);
      });
    });

    // Скидання до стандартних
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        currentSettings = Object.assign({}, DEFAULT_SETTINGS);
        saveSettings(currentSettings);
        applySettings(currentSettings);
      });
    }
  }

  // Запуск ініціалізації
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initA11yListeners);
  } else {
    initA11yListeners();
  }

  // Експорт у глобальну область для можливих викликів з інших скриптів
  window.AvatarAI_A11y = window.TeachAI_A11y = {
    getSettings,
    saveSettings,
    applySettings
  };
})();
