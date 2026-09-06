"""
Tool Registry defining function definitions and schemas for LLM tool calling.
Follows OpenAI / Gemini compatible tool format.
Includes complete Facebook Page Management, Messaging, Comments, Insights, and Advertising tools.
"""

from typing import List, Dict, Any

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    # --- FACEBOOK PAGE MANAGEMENT & PUBLISHING ---
    {
        "type": "function",
        "function": {
            "name": "get_facebook_page_overview",
            "description": "Get current Facebook Page profile, follower count, category, rating, and status.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_facebook",
            "description": "Publish a text post or photo post to your Facebook Page feed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The post content/caption for Facebook including emojis and hashtags."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional public URL or file path of the image to post."
                    }
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "publish_facebook_ad_post",
            "description": "Publish a high-converting sponsored or action-driven ad post with a Call-To-Action (CTA) button (e.g. LEARN_MORE, SHOP_NOW, SIGN_UP, CONTACT_US) and destination link on your Facebook Page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Engaging marketing copy and ad text with emojis and hook."
                    },
                    "link": {
                        "type": "string",
                        "description": "Destination landing page, website URL, or WhatsApp link."
                    },
                    "cta_type": {
                        "type": "string",
                        "enum": ["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US", "BOOK_TRAVEL", "GET_QUOTE", "APPLY_NOW", "SUBSCRIBE"],
                        "description": "The action button displayed on the post. Default is LEARN_MORE."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional image URL for the ad post."
                    }
                },
                "required": ["message", "link"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_facebook_ad_campaign",
            "description": "Create a new Ad Campaign in the user's Meta Ad Account via Marketing API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the ad campaign."
                    },
                    "objective": {
                        "type": "string",
                        "enum": ["OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT", "OUTCOME_LEADS", "OUTCOME_SALES"],
                        "description": "Campaign objective. Default is OUTCOME_TRAFFIC."
                    },
                    "daily_budget": {
                        "type": "integer",
                        "description": "Daily budget in USD (e.g. 10 for $10/day)."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_facebook_posts_and_insights",
            "description": "Fetch recent Facebook Page posts with likes, comments, shares, and engagement performance metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent posts to retrieve (default 5)."
                    }
                }
            }
        }
    },
    # --- FACEBOOK MESSAGING & COMMENTS ---
    {
        "type": "function",
        "function": {
            "name": "get_facebook_inbox",
            "description": "Fetch customer Messenger conversations from the Facebook Page Inbox, showing customer names, message previews, and unread statuses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of conversation threads to fetch (default 10)."
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Filter for unread conversations only."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversation_messages",
            "description": "Fetch message history from a specific customer conversation thread in Facebook Inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "The conversation thread ID (from get_facebook_inbox)."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to retrieve (default 10)."
                    }
                },
                "required": ["conversation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_facebook_message",
            "description": "Send a reply to a customer in their Facebook Messenger conversation thread.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "The conversation thread ID to reply to."
                    },
                    "message": {
                        "type": "string",
                        "description": "The message text to send to the customer."
                    }
                },
                "required": ["conversation_id", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_facebook_post_comments",
            "description": "Fetch comments on a specific Facebook post to see customer inquiries, praise, or questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "The Facebook Post ID."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of comments to fetch (default 20)."
                    }
                },
                "required": ["post_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_facebook_comment",
            "description": "Reply directly to a user's comment on a Facebook post.",
            "parameters": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "The comment ID to reply to."
                    },
                    "message": {
                        "type": "string",
                        "description": "The reply message text."
                    }
                },
                "required": ["comment_id", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_reply_to_comment_in_language",
            "description": "Analyze a Facebook comment, detect its language (e.g. Somali, English, Arabic, Swahili, etc.), and generate a contextual, polite response in the exact same language matching the commenter's tone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "The comment ID to reply to."
                    },
                    "comment_text": {
                        "type": "string",
                        "description": "The original text of the comment to analyze and reply to."
                    },
                    "detected_language": {
                        "type": "string",
                        "description": "The language detected from the comment (e.g. 'Somali', 'English', 'Arabic', 'Swahili')."
                    },
                    "reply_message": {
                        "type": "string",
                        "description": "The drafted response in the detected language with emojis and polite tone."
                    }
                },
                "required": ["comment_id", "comment_text", "reply_message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_page_comments",
            "description": "Fetch recent customer comments across all latest posts on the Facebook Page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of comments to fetch (default 15)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_facebook_post",
            "description": "Schedule a post to be published automatically at a future time on your Facebook Page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The post content with hashtags and emojis."
                    },
                    "publish_timestamp": {
                        "type": "integer",
                        "description": "Unix timestamp in seconds for when the post should be published (at least 10 minutes in the future)."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional image URL."
                    }
                },
                "required": ["message", "publish_timestamp"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "post_video_to_facebook",
            "description": "Publish a video or Reel to your Facebook Page with title and description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_url": {
                        "type": "string",
                        "description": "URL or local path of the video file."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the video or Reel."
                    },
                    "description": {
                        "type": "string",
                        "description": "Description/caption for the video post with tags."
                    }
                },
                "required": ["video_url", "title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "moderate_facebook_comment",
            "description": "Moderate a comment on a Facebook post (hide, unhide, or delete).",
            "parameters": {
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "The comment ID to moderate."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["hide", "unhide", "delete"],
                        "description": "Action to perform: 'hide', 'unhide', or 'delete'."
                    }
                },
                "required": ["comment_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_facebook_page_analytics",
            "description": "Fetch overall Facebook Page analytics including page impressions, page views, and engagement trends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["day", "week", "days_28"],
                        "description": "Metric period: 'day', 'week', or 'days_28'. Default is 'day'."
                    }
                }
            }
        }
    },
    # --- INSTAGRAM & CROSS POSTING ---
    {
        "type": "function",
        "function": {
            "name": "post_to_instagram",
            "description": "Publish a photo post with caption to your Instagram Business Account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "Public URL of the photo to publish on Instagram (required)."
                    },
                    "caption": {
                        "type": "string",
                        "description": "The caption for Instagram including hook, line breaks, emojis, and hashtags."
                    }
                },
                "required": ["image_url", "caption"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cross_post_meta",
            "description": "Simultaneously publish a photo and caption to BOTH Facebook Page and Instagram Account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "Public URL of the photo to publish."
                    },
                    "caption": {
                        "type": "string",
                        "description": "The post caption tailored for both Facebook and Instagram."
                    }
                },
                "required": ["image_url", "caption"]
            }
        }
    },
    # --- WHATSAPP ---
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": "Send a WhatsApp message or image to a contact or phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_phone": {
                        "type": "string",
                        "description": "Phone number with country code (e.g. +252615000000 or 15551234567)."
                    },
                    "message": {
                        "type": "string",
                        "description": "The message body to send."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional image URL to send alongside the message."
                    }
                },
                "required": ["recipient_phone", "message"]
            }
        }
    },
    # --- GMAIL ---
    {
        "type": "function",
        "function": {
            "name": "read_unread_emails",
            "description": "Check and summarize unread emails in your Gmail inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of unread emails to retrieve (default 5)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Compose and send an email from your Gmail account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line."
                    },
                    "body": {
                        "type": "string",
                        "description": "Plain text body of the email."
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Save a draft email in your Gmail Drafts folder without sending it immediately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line."
                    },
                    "body": {
                        "type": "string",
                        "description": "Draft email body."
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    # --- SUBSTACK ---
    {
        "type": "function",
        "function": {
            "name": "create_substack_post",
            "description": "Draft a newsletter article on Substack with title, subtitle, and body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Post headline/title."
                    },
                    "subtitle": {
                        "type": "string",
                        "description": "Brief subtitle or lead-in summary."
                    },
                    "body": {
                        "type": "string",
                        "description": "The markdown or text content of the article."
                    }
                },
                "required": ["title", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "post_substack_note",
            "description": "Publish a short-form Note on Substack (like a tweet/thread).",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content of the Substack Note."
                    }
                },
                "required": ["content"]
            }
        }
    },
    # --- GENERAL SOCIAL OVERVIEW & N8N ---
    {
        "type": "function",
        "function": {
            "name": "get_social_overview",
            "description": "Fetch recent activity, latest posts, and status across all connected platforms.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_n8n_automation",
            "description": "Trigger an automated workflow on your n8n instance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_name_or_webhook": {
                        "type": "string",
                        "description": "The webhook name or path of the n8n workflow."
                    },
                    "data": {
                        "type": "object",
                        "description": "Key-value parameters to pass to the workflow."
                    }
                },
                "required": ["workflow_name_or_webhook"]
            }
        }
    }
]
