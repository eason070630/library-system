from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap 5 CSS classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            css = 'form-select' if isinstance(w, forms.Select) else 'form-control'
            w.attrs['class'] = (w.attrs.get('class', '') + ' ' + css).strip()
