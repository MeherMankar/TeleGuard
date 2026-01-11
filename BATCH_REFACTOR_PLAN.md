# Batch Refactoring Plan - All 137 Functions

## Strategy
Refactor all 137 complex functions systematically by priority (highest complexity first).

## Top 20 Priority Targets

1. ✅ message_handlers.py:_handle_user_reply (98→<10) - DONE
2. ✅ session_export_handler.py:_create_fresh_session (67→<10) - DONE  
3. ⏳ admin_handlers.py:register_handlers (72) - IN PROGRESS
4. command_handlers.py:register_handlers (65)
5. session_export_handler.py:process_fresh_session_otp (60)
6. advanced_spam_handler.py:register_handlers (53)
7. spam_filters_handler.py:register_handlers (46)
8. auto_reply_handler.py:setup_auto_reply_menu (43)
9. contact_handler.py:register_handlers (40)
10. session_login_handler.py:_execute_session_creation (39)
11. bot_manager.py:_start_user_client (38)
12. session_export_handler.py:process_fresh_session_2fa (37)
13. otp_destroyer.py:setup_otp_listener (34)
14. bulk_sender.py:register_handlers (33)
15. dm_reply_handler.py:_setup_bot_handlers (32)
16. bulk_sender.py:_execute_bulk_job (31)
17. otp_manager.py:setup_handler_for_new_client (30)
18. spam_appeal_handler.py:register_handlers (30)
19. dm_reply_handler.py:_setup_client_dm_handler (29)
20. account_cleaner.py:get_cleanup_preview (28)

## Refactoring Approach

For each function:
1. Extract validation logic → helper methods
2. Extract business logic → focused methods  
3. Extract error handling → dedicated handlers
4. Use action maps for routing
5. Apply early returns
6. Single responsibility per method

## Progress Tracking
- Total: 137 functions
- Completed: 2
- Remaining: 135
- Estimated time: 50-60 hours
