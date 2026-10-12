/**
 * TeachAI Accessibility & Theme Manager
 * Керує:
 * - Світлою / Нічною темами
 * - Масштабуванням контенту для людей з порушенням зору (A / A+ / A++)
 * - Режимами для дальтоніків (Протанопія, Дейтеранопія, Тританопія, Високий контраст)
 * - Збереженням у localStorage та миттєвим застосуванням без перезавантаження
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'teachai_a11y_settings';

  const DEFAULT_SETTINGS = {
    theme: 'light',
    fontScale: 'normal',
    colorblind: 'none'
  };

  /**
   * Отримати збережені або стандартні налаштування
   */
  function getSettings() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
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
      iconEl.textContent = '☀️';
      btnEl.setAttribute('aria-label', 'Перемкнути на світлу тему');
      btnEl.setAttribute('title', 'Увімкнути світлу тему');
    } else {
      iconEl.textContent = '🌙';
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
  window.TeachAI_A11y = {
    getSettings,
    saveSettings,
    applySettings
  };
})();
