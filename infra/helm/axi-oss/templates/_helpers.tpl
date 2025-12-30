{{/*
Expand the name of the chart.
*/}}
{{- define "axi-oss.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "axi-oss.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "axi-oss.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "axi-oss.labels" -}}
helm.sh/chart: {{ include "axi-oss.chart" . }}
{{ include "axi-oss.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "axi-oss.selectorLabels" -}}
app.kubernetes.io/name: {{ include "axi-oss.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "axi-oss.api.selectorLabels" -}}
{{ include "axi-oss.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "axi-oss.frontend.selectorLabels" -}}
{{ include "axi-oss.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "axi-oss.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "axi-oss.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
API image
*/}}
{{- define "axi-oss.api.image" -}}
{{- $tag := default .Chart.AppVersion .Values.api.image.tag }}
{{- printf "%s:%s" .Values.api.image.repository $tag }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "axi-oss.frontend.image" -}}
{{- $tag := default .Chart.AppVersion .Values.frontend.image.tag }}
{{- printf "%s:%s" .Values.frontend.image.repository $tag }}
{{- end }}

{{/*
Database URL for PostgreSQL storage
*/}}
{{- define "axi-oss.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- $host := printf "%s-postgresql" (include "axi-oss.fullname" .) }}
{{- $port := "5432" }}
{{- $user := .Values.postgresql.auth.username }}
{{- $db := .Values.postgresql.auth.database }}
{{- printf "postgres://%s:$(DB_PASSWORD)@%s:%s/%s" $user $host $port $db }}
{{- else if .Values.externalPostgresql.host }}
{{- $host := .Values.externalPostgresql.host }}
{{- $port := .Values.externalPostgresql.port | toString }}
{{- $user := .Values.externalPostgresql.username }}
{{- $db := .Values.externalPostgresql.database }}
{{- printf "postgres://%s:$(DB_PASSWORD)@%s:%s/%s" $user $host $port $db }}
{{- end }}
{{- end }}

{{/*
Secret name
*/}}
{{- define "axi-oss.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "axi-oss.fullname" .) }}
{{- end }}
{{- end }}
