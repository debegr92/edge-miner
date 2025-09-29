def parseBool(value) -> bool:
	if isinstance(value, bool):
		return value
	elif isinstance(value, str):
		if len(value) > 0 and value.lower() in ['1', 'true', 't', 'yes', 'y']:
			return True
	return False