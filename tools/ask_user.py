
def get_user_input(**kwargs):
    """
    Provide the information to the user and receive input from user.
    """
    print("Please provide the following information:")
    for key, value in kwargs.items():
        print(f"{key}: {value}")
    user_input = input("You: ")
    return user_input, ""