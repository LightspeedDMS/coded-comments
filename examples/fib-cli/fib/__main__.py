import sys

from .cli import main

#^ hazard removing this => ValueError printing results >4300 digits on CPython 3.9.14+ (int->str cap); hasattr: older builds lack the API
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

sys.exit(main())
