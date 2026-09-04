"""
Tool Registry defining function definitions and schemas for LLM tool calling.
Follows OpenAI / Gemini compatible tool format.
"""

from typing import List, Dict, Any

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "post_to_facebook",
            "description": "Publish a text post or photo post to your Facebook Page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The post content/caption for Facebook including emojis and hashtags."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional public URL of the image to post."
                    }
                },
                "required": ["message"]
            }
        }
    },
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
