async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command with an enhanced inline keyboard for all features"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "User"
    chat_type = update.effective_chat.type

    if chat_type == 'private' and user_id != ADMIN_USER_ID:
        response, reply_markup = await self.get_private_chat_redirect()
        await update.message.reply_text(response, reply_markup=reply_markup)
    else:
        # Define the inline keyboard with all features
        keyboard = [
            [
                InlineKeyboardButton("Start", callback_data="start"),
                InlineKeyboardButton("Help", callback_data="help"),
                InlineKeyboardButton("User Info", callback_data="info")
            ],
            [
                InlineKeyboardButton("Check Email", callback_data="checkmail"),
                InlineKeyboardButton("Bot Status", callback_data="status"),
                InlineKeyboardButton("Clear History", callback_data="clear")
            ],
            [
                InlineKeyboardButton("Join Group", url="https://t.me/VPSHUB_BD_CHAT")
            ]
        ]
        # Add admin-only buttons if the user is the admin
        if user_id == ADMIN_USER_ID:
            keyboard.append([
                InlineKeyboardButton("Set API Key", callback_data="api"),
                InlineKeyboardButton("Change Model", callback_data="setmodel"),
                InlineKeyboardButton("Set Admin", callback_data="setadmin")
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🌟 Hello {username}, explore I Master Tools' features below! 🌟\n"
            "Choose an option to get started:",
            reply_markup=reply_markup
        )

async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks for all menu features"""
    query = update.callback_query
    callback_data = query.data
    await query.answer()  # Acknowledge the button press

    # Map callback data to command handlers
    command_mapping = {
        "start": self.start_command,
        "help": self.help_command,
        "clear": self.clear_command,
        "status": self.status_command,
        "checkmail": self.checkmail_command,
        "info": self.info_command,
        "api": self.api_command,
        "setmodel": self.setmodel_command,
        "setadmin": self.setadmin_command,
        "copy_code": lambda u, c: query.answer("Code copied!")  # Existing copy_code handler
    }

    if callback_data in command_mapping:
        # For commands requiring arguments (e.g., /api, /setmodel, /info with args), prompt for input
        if callback_data in ["api", "setmodel"]:
            if callback_data == "api":
                await query.message.reply_text(
                    "Please provide the Gemini API key using: /api <your_api_key>",
                    parse_mode='Markdown'
                )
            elif callback_data == "setmodel":
                models_list = "\n".join([f"- {model}" for model in available_models])
                await query.message.reply_text(
                    f"Available models:\n{models_list}\n\nPlease use: /setmodel <model_name>"
                )
        elif callback_data == "info":
            await query.message.reply_text(
                "To view user info, use: /info or /info <@username> or /info <user_id>"
            )
        else:
            # Execute the command handler, passing the update and context
            await command_mapping[callback_data](query, context)
    else:
        await query.message.reply_text("Unknown action. Please try another option from the menu!")