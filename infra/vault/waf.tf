# ============================================================
# KMRL NexusAI — WAF & Network Security Configuration
# AWS WAF v2 + Cloudflare Rules
# ============================================================

# ── Terraform: AWS WAF WebACL ─────────────────────────────────────────────

resource "aws_wafv2_web_acl" "kmrl_waf" {
  name        = "kmrl-nexusai-waf"
  description = "KMRL NexusAI Web Application Firewall"
  scope       = "REGIONAL"  # use CLOUDFRONT for CF distribution

  default_action {
    allow {}
  }

  # ── Rule 1: AWS Managed Common Rule Set ──────────────────────────────
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        # Exclude rules that block legitimate API payloads
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}   # count instead of block for large JSON payloads
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 2: AWS Known Bad Inputs ──────────────────────────────────────
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "KnownBadInputsMetric"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 3: SQL Injection Protection ─────────────────────────────────
  rule {
    name     = "SQLiProtection"
    priority = 3

    action {
      block {}
    }

    statement {
      sqli_match_statement {
        field_to_match {
          all_query_arguments {}
        }
        text_transformations {
          priority = 1
          type     = "URL_DECODE"
        }
        text_transformations {
          priority = 2
          type     = "HTML_ENTITY_DECODE"
        }
        sensitivity_level = "HIGH"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiProtectionMetric"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 4: XSS Protection ────────────────────────────────────────────
  rule {
    name     = "XSSProtection"
    priority = 4

    action {
      block {}
    }

    statement {
      xss_match_statement {
        field_to_match {
          all_query_arguments {}
        }
        text_transformations {
          priority = 1
          type     = "URL_DECODE"
        }
        text_transformations {
          priority = 2
          type     = "HTML_ENTITY_DECODE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "XSSProtectionMetric"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 5: Rate Limiting (Auth endpoints) ───────────────────────────
  rule {
    name     = "AuthRateLimit"
    priority = 5

    action {
      block {
        custom_response {
          response_code = 429
          custom_response_body_key = "rate_limit_response"
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 100    # 100 requests per 5 minutes per IP
        aggregate_key_type = "IP"

        scope_down_statement {
          byte_match_statement {
            search_string = "/api/v1/auth/"
            field_to_match {
              uri_path {}
            }
            text_transformations {
              priority = 0
              type     = "NONE"
            }
            positional_constraint = "STARTS_WITH"
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AuthRateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  # ── Rule 6: Geo-Restriction ────────────────────────────────────────────
  rule {
    name     = "GeoRestriction"
    priority = 6

    action {
      block {}
    }

    statement {
      not_statement {
        statement {
          geo_match_statement {
            country_codes = ["IN"]    # allow India only
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "GeoRestrictionMetric"
      sampled_requests_enabled   = false
    }
  }

  # ── Rule 7: IP Allowlist for Admin endpoints ──────────────────────────
  rule {
    name     = "AdminIPAllowlist"
    priority = 7

    action {
      block {}
    }

    statement {
      and_statement {
        statement {
          not_statement {
            statement {
              ip_set_reference_statement {
                arn = aws_wafv2_ip_set.kmrl_admin_ips.arn
              }
            }
          }
        }
        statement {
          byte_match_statement {
            search_string = "/api/v1/admin/"
            field_to_match {
              uri_path {}
            }
            text_transformations {
              priority = 0
              type     = "NONE"
            }
            positional_constraint = "STARTS_WITH"
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AdminIPAllowlistMetric"
      sampled_requests_enabled   = true
    }
  }

  custom_response_bodies {
    key          = "rate_limit_response"
    content_type = "APPLICATION_JSON"
    content      = jsonencode({
      error      = "Rate limit exceeded. Please try again in 5 minutes."
      status_code = 429
    })
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "KMRLNexusAIWAF"
    sampled_requests_enabled   = true
  }

  tags = {
    Environment = "production"
    Project     = "kmrl-nexusai"
    ManagedBy   = "terraform"
  }
}

# ── Admin IP Set ──────────────────────────────────────────────────────────
resource "aws_wafv2_ip_set" "kmrl_admin_ips" {
  name               = "kmrl-admin-ips"
  description        = "Allowed IPs for KMRL admin endpoints"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"

  addresses = [
    "103.x.x.x/32",    # KMRL HQ - Ernakulam
    "202.x.x.x/32",    # KMRL IT Office
    "10.0.0.0/8",      # Internal Kubernetes cluster
  ]
}

# ── WAF Association ───────────────────────────────────────────────────────
resource "aws_wafv2_web_acl_association" "kmrl_alb" {
  resource_arn = aws_lb.kmrl_alb.arn
  web_acl_arn  = aws_wafv2_web_acl.kmrl_waf.arn
}

# ── WAF Logging ───────────────────────────────────────────────────────────
resource "aws_wafv2_web_acl_logging_configuration" "kmrl_waf_logs" {
  log_destination_configs = [aws_cloudwatch_log_group.waf_logs.arn]
  resource_arn            = aws_wafv2_web_acl.kmrl_waf.arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  logging_filter {
    default_behavior = "DROP"

    filter {
      behavior    = "KEEP"
      requirement = "MEETS_ANY"

      condition {
        action_condition {
          action = "BLOCK"
        }
      }
    }
  }
}

resource "aws_cloudwatch_log_group" "waf_logs" {
  name              = "/aws/wafv2/kmrl-nexusai"
  retention_in_days = 90

  tags = {
    Project = "kmrl-nexusai"
  }
}

# ── Cloudflare Page Rules (alternative / CDN layer) ──────────────────────
# Configure in Cloudflare dashboard or Terraform cloudflare provider:
#
# Rule 1: Security Level High for /api/v1/auth/*
# Rule 2: Cache Level Bypass for all API routes
# Rule 3: Always HTTPS
# Rule 4: HSTS max-age=31536000; includeSubDomains; preload
# Rule 5: Bot Fight Mode ON
# Rule 6: Under Attack Mode trigger at >10k req/min
#
# Cloudflare Workers rate limiting:
# - /api/v1/auth/token: 10 req/min per IP
# - /api/v1/induction/optimize: 5 req/min per user
# - All others: 120 req/min per IP
