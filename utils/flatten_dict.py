def flatten_dict(d):
    items = []
    for k, v in d.items():
        new_key = f"{k}" 
        if isinstance(v, dict):
            items.extend(flatten_dict(v).items())
        else:
            items.append((new_key, v))
    return dict(items)