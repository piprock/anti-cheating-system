# CSS Architecture

## Структура файлів

### Базові стилі
- **`style.css`** - Глобальні змінні, скидання стилів, базова типографіка
- **`header.css`** - Стилі для шапки сайту та навігації
- **`footer.css`** - Стилі для футера

### Компоненти
- **`buttons.css`** - Усі стилі кнопок та CTA елементів
- **`forms.css`** - Стилі форм, інпутів, лейблів
- **`content.css`** - Стилі основних контентних блоків (питання-відповідь, intro секція)

### Утиліти
- **`layout.css`** - Flexbox/Grid утиліти, відступи, картки, медіа контейнери

## Принципи

1. **Без inline стилів** - Всі стилі винесені в окремі CSS файли
2. **Без absolute positioning** - Використовуємо flexbox/grid для розміщення
3. **Модульність** - Кожен файл відповідає за свою область
4. **Класи замість inline** - HTML використовує семантичні класи

## Приклади використання

### Кнопки
```html
<button class="btn">Звичайна кнопка</button>
<button class="btn btn-green">Зелена кнопка</button>
<button class="btn btn-small">Маленька кнопка</button>
```

### Layout
```html
<div class="flex-between gap-md">
  <div>Ліворуч</div>
  <div>Праворуч</div>
</div>

<div class="video-controls">
  <button>Кнопка 1</button>
  <button>Кнопка 2</button>
</div>
```

### Форми
```html
<div class="form-group">
  <label for="name">Ім'я:</label>
  <input type="text" id="name" class="input-medium">
  <button>Відправити</button>
</div>
```

## Порядок підключення в base.html

```html
<link rel="stylesheet" href="{% static "css/style.css" %}">
<link rel="stylesheet" href="{% static "css/footer.css" %}">
<link rel="stylesheet" href="{% static "css/header.css" %}">
<link rel="stylesheet" href="{% static "css/buttons.css" %}">
<link rel="stylesheet" href="{% static "css/layout.css" %}">
<link rel="stylesheet" href="{% static "css/forms.css" %}">
{% block css %}{% endblock css %}
```

## Змінні (в style.css)

```css
:root {
  --green: #3FA72F;
  --orange: #FF8225;
  --black: #252525;
}
```
