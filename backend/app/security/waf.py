"""
KMRL NexusAI — WAF & Network Security Configuration
=====================================================
Implements government-grade security perimeter:

Layer 1: Cloudflare WAF (edge, DDoS mitigation)
Layer 2: AWS WAF v2 (application layer rules)
Layer 3: NGINX rate limiting (origin protection)
Layer 4: FastAPI middleware (request validation)

Deployed as Terraform / AWS CDK compatible configuration.
"""
from __future__ import annotations

# ── AWS WAF v2 WebACL Configuration ──────────────────────────────────────
# Deploy with: terraform apply or aws cloudformation deploy

AWS_WAF_WEBACL = {
    "Name": "KMRLNexusAI-WAF",
    "Scope": "REGIONAL",                     # or CLOUDFRONT for CDN
    "DefaultAction": {"Allow": {}},
    "Description": "KMRL NexusAI Platform WAF — Government-grade protection",
    "Rules": [

        # Rule 1: AWS Managed — Core Rule Set (OWASP Top 10)
        {
            "Name": "AWSManagedRulesCoreRuleSet",
            "Priority": 1,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesCommonRuleSet",
                    "ExcludedRules": [],
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-core-rule-set",
            },
        },

        # Rule 2: AWS Managed — Known Bad Inputs
        {
            "Name": "AWSManagedRulesKnownBadInputsRuleSet",
            "Priority": 2,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesKnownBadInputsRuleSet",
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-bad-inputs",
            },
        },

        # Rule 3: AWS Managed — SQL Injection protection
        {
            "Name": "AWSManagedRulesSQLiRuleSet",
            "Priority": 3,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesSQLiRuleSet",
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-sqli",
            },
        },

        # Rule 4: Auth endpoint — strict rate limit (10 req/5min per IP)
        {
            "Name": "AuthEndpointRateLimit",
            "Priority": 10,
            "Action": {"Block": {}},
            "Statement": {
                "RateBasedStatement": {
                    "Limit": 10,
                    "EvaluationWindowSec": 300,
                    "AggregateKeyType": "IP",
                    "ScopeDownStatement": {
                        "ByteMatchStatement": {
                            "SearchString": "/api/v1/auth/token",
                            "FieldToMatch": {"UriPath": {}},
                            "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
                            "PositionalConstraint": "STARTS_WITH",
                        }
                    },
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-auth-rate-limit",
            },
        },

        # Rule 5: Optimizer endpoint — limit to 2 req/min per IP
        # (prevents optimizer abuse / resource exhaustion)
        {
            "Name": "OptimizerRateLimit",
            "Priority": 11,
            "Action": {"Block": {}},
            "Statement": {
                "RateBasedStatement": {
                    "Limit": 2,
                    "EvaluationWindowSec": 60,
                    "AggregateKeyType": "IP",
                    "ScopeDownStatement": {
                        "ByteMatchStatement": {
                            "SearchString": "/api/v1/induction/optimize",
                            "FieldToMatch": {"UriPath": {}},
                            "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
                            "PositionalConstraint": "STARTS_WITH",
                        }
                    },
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-optimizer-rate-limit",
            },
        },

        # Rule 6: Block non-India IPs (government compliance)
        # Allowlist: India (IN), internal VPN ranges
        {
            "Name": "GeoRestriction",
            "Priority": 20,
            "Action": {"Block": {}},
            "Statement": {
                "NotStatement": {
                    "Statement": {
                        "OrStatement": {
                            "Statements": [
                                # Allow India
                                {
                                    "GeoMatchStatement": {
                                        "CountryCodes": ["IN"]
                                    }
                                },
                                # Allow known VPN/office IPs (update with real IPs)
                                {
                                    "IPSetReferenceStatement": {
                                        "ARN": "arn:aws:wafv2:ap-south-1:ACCOUNT:regional/ipset/kmrl-allowlist/ID"
                                    }
                                },
                            ]
                        }
                    }
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-geo-restriction",
            },
        },

        # Rule 7: Block bad bots and scrapers
        {
            "Name": "AWSManagedRulesBotControlRuleSet",
            "Priority": 30,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesBotControlRuleSet",
                    "ManagedRuleGroupConfigs": [
                        {"AWSManagedRulesBotControlRuleSet": {"InspectionLevel": "COMMON"}}
                    ],
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-bot-control",
            },
        },

        # Rule 8: Require valid Content-Type for POST/PUT
        {
            "Name": "RequireJsonContentType",
            "Priority": 40,
            "Action": {"Block": {}},
            "Statement": {
                "AndStatement": {
                    "Statements": [
                        # Is a POST or PUT
                        {
                            "OrStatement": {
                                "Statements": [
                                    {
                                        "ByteMatchStatement": {
                                            "SearchString": "POST",
                                            "FieldToMatch": {"Method": {}},
                                            "TextTransformations": [{"Priority": 0, "Type": "UPPERCASE"}],
                                            "PositionalConstraint": "EXACTLY",
                                        }
                                    },
                                    {
                                        "ByteMatchStatement": {
                                            "SearchString": "PUT",
                                            "FieldToMatch": {"Method": {}},
                                            "TextTransformations": [{"Priority": 0, "Type": "UPPERCASE"}],
                                            "PositionalConstraint": "EXACTLY",
                                        }
                                    },
                                ]
                            }
                        },
                        # Does NOT have application/json content type
                        {
                            "NotStatement": {
                                "Statement": {
                                    "ByteMatchStatement": {
                                        "SearchString": "application/json",
                                        "FieldToMatch": {
                                            "SingleHeader": {"Name": "content-type"}
                                        },
                                        "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
                                        "PositionalConstraint": "CONTAINS",
                                    }
                                }
                            }
                        },
                        # Is targeting the API (not form submission endpoints)
                        {
                            "ByteMatchStatement": {
                                "SearchString": "/api/v1/",
                                "FieldToMatch": {"UriPath": {}},
                                "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
                                "PositionalConstraint": "STARTS_WITH",
                            }
                        },
                    ]
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-content-type",
            },
        },

        # Rule 9: Size restriction — block oversized request bodies (>1MB)
        {
            "Name": "BlockOversizedBodies",
            "Priority": 50,
            "Action": {"Block": {}},
            "Statement": {
                "SizeConstraintStatement": {
                    "FieldToMatch": {"Body": {"OversizeHandling": "MATCH"}},
                    "ComparisonOperator": "GT",
                    "Size": 1_048_576,   # 1 MB
                    "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
                }
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "kmrl-body-size",
            },
        },
    ],

    "VisibilityConfig": {
        "SampledRequestsEnabled": True,
        "CloudWatchMetricsEnabled": True,
        "MetricName": "KMRLNexusAIWebACL",
    },

    "Tags": [
        {"Key": "Project",     "Value": "KMRL NexusAI"},
        {"Key": "Environment", "Value": "production"},
        {"Key": "Owner",       "Value": "platform-team@kmrl.in"},
        {"Key": "ManagedBy",   "Value": "terraform"},
    ],
}


# ── Cloudflare WAF Rules (Zone Rules) ────────────────────────────────────

CLOUDFLARE_RULES = [
    {
        "description": "Block non-India traffic (government compliance)",
        "expression":  'not ip.geoip.country in {"IN"}',
        "action":      "block",
        "enabled":     True,
        "priority":    1,
    },
    {
        "description": "Challenge suspicious bots",
        "expression":  "(cf.threat_score gt 14 and not cf.verified_bot_category in {\"search_engine\"})",
        "action":      "managed_challenge",
        "enabled":     True,
        "priority":    2,
    },
    {
        "description": "Rate limit auth endpoint",
        "expression":  'http.request.uri.path eq "/api/v1/auth/token"',
        "action":      "rate_limit",
        "ratelimit": {
            "characteristics":     ["cf.colo.id", "ip.src"],
            "period":              300,
            "requests_per_period": 10,
            "mitigation_timeout":  600,
        },
        "enabled":  True,
        "priority": 3,
    },
    {
        "description": "Allow monitoring IPs unrestricted",
        "expression":  "ip.src in {10.0.0.0/8 172.16.0.0/12 192.168.0.0/16}",
        "action":      "skip",
        "enabled":     True,
        "priority":    100,
    },
]


# ── FastAPI Security Middleware ───────────────────────────────────────────

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    HEADERS = {
        "X-Content-Type-Options":    "nosniff",
        "X-Frame-Options":           "DENY",
        "X-XSS-Protection":          "1; mode=block",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Referrer-Policy":           "strict-origin-when-cross-origin",
        "Permissions-Policy":        "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "       # Next.js requires unsafe-inline
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' wss://api.nexusai.kmrl.in https://api.nexusai.kmrl.in; "
            "img-src 'self' data: blob:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'"
        ),
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in self.HEADERS.items():
            response.headers[header] = value
        # Remove server version disclosure
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        return response


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests with body exceeding MAX_SIZE."""
    MAX_SIZE = 10 * 1024 * 1024   # 10 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_SIZE:
            return JSONResponse(
                status_code=413,
                content={"error": "Request body too large", "max_bytes": self.MAX_SIZE},
            )
        return await call_next(request)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Enforce API versioning — reject unversioned API calls."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v"):
            return JSONResponse(
                status_code=400,
                content={"error": "API version required. Use /api/v1/..."},
            )
        return await call_next(request)


def apply_security_middleware(app: FastAPI) -> None:
    """Apply all security middleware to FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeMiddleware)
    app.add_middleware(APIVersionMiddleware)
