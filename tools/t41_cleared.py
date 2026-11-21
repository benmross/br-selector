# Main's selector with could_raise cleared (every t41 patch is tok-str only,
# so this equals clearing just the tok-str branch). Analysis only.
import sys
sys.path.insert(0, '.')
sys.argv = ['selector.py']
import selector
selector.could_raise = lambda *a, **k: False
selector.main()
