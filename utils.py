def get_display_name(user):
    if nick := user.nick:
        return nick
    return user.name
