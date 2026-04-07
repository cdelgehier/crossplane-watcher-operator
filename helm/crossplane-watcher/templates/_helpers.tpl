{{/*
Expand the name of the chart.
*/}}
{{- define "crossplane-watcher.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fullname — used for all resource names.
*/}}
{{- define "crossplane-watcher.fullname" -}}
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
Common labels.
*/}}
{{- define "crossplane-watcher.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "crossplane-watcher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "crossplane-watcher.selectorLabels" -}}
app.kubernetes.io/name: {{ include "crossplane-watcher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "crossplane-watcher.serviceAccountName" -}}
{{- if .Values.serviceAccount.name }}
{{- .Values.serviceAccount.name }}
{{- else }}
{{- include "crossplane-watcher.fullname" . }}
{{- end }}
{{- end }}

{{/*
Secret name (existing or generated).
*/}}
{{- define "crossplane-watcher.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "crossplane-watcher.fullname" . }}
{{- end }}
{{- end }}

{{/*
Container image reference.
*/}}
{{- define "crossplane-watcher.image" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag -}}
{{- if not (hasPrefix "v" $tag) -}}{{- $tag = printf "v%s" $tag -}}{{- end -}}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.repository $tag -}}
{{- end }}
