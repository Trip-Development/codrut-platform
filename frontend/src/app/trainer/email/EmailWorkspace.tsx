"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2Icon, PlusIcon, UploadIcon } from "lucide-react";
import {
  listEmailTemplatesOnServer,
  createEmailTemplateOnServer,
  updateEmailTemplateOnServer,
  deleteEmailTemplateOnServer,
  deleteCampaignOnServer,
  deleteCampaignAssetOnServer,
  archiveCampaignRecipientOnServer,
  bulkCreateCampaignRecipientsOnServer,
  buildVideoCampaignCreatePayload,
  createCampaignOnServer,
  getEmailOpsSummary,
  getEmailSendCapacity,
  htmlToPlainText,
  listCampaignRecipientMembershipOnServer,
  listCampaignsOnServer,
  permanentlyDeleteCampaignRecipientOnServer,
  replaceCampaignRecipientMembershipOnServer,
  restoreCampaignRecipientOnServer,
  sendCampaignOnServer,
  updateCampaignOnServer,
  updateCampaignRecipientOnServer,
  uploadCampaignAssetOnServer,
  campaignAssetFileNameFromUrl,
  CampaignPersistenceError,
  type EmailOpsSummary,
  type EmailSendCapacity,
  type CampaignRecipientRow,
  type CampaignSendResponse,
  type EmailCampaign,
  type CampaignCreate,
  type EmailTemplate
} from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { ModalLayer } from "@/components/ui/modal-layer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUrlState } from "@/hooks/use-url-state";
import { readSpreadsheetFile, spreadsheetRowsToObjects } from "@/utils/spreadsheet-import";
import { EmailWorkspaceNavigation, type EmailWorkspaceView } from "./EmailWorkspaceNavigation";
import { ArchivedContactsWorkspaceView } from "./ArchivedContactsWorkspaceView";
import { CampaignEditorModal } from "./CampaignEditorModal";
import { CampaignsWorkspaceView } from "./CampaignsWorkspaceView";
import { ContactImportModal, ManualContactModal } from "./ContactImportModals";
import { ContactsWorkspaceView } from "./ContactsWorkspaceView";
import { TemplatesWorkspaceView } from "./TemplatesWorkspaceView";
import {
  campaignRecipientCompanyKey,
  campaignRecipientDraft,
  campaignRecipientMatchesSearch,
  campaignRecipientName,
  campaignRecipientSegment,
  campaignRecipientSortKey,
  campaignSendFailureDetail,
  campaignSendResultSummary,
  createCampaignSendIdempotencyKey,
  isCampaignRecipientEffectivelyActive,
  splitContactName,
  type CampaignContactDraft,
  type CampaignContactTypeFilter,
  type CampaignDeliveryState,
  type CampaignSendMode,
  type CampaignTargetSegment,
} from "./campaign-domain";
import {
  buildCampaignRecipientImportDrafts,
  campaignImportDraftToRecipient,
  importDraftHasEmailError,
  isValidImportEmail,
  selectCampaignRecipientImportSheetName,
  uniqueCampaignImportDrafts,
  type CampaignImportDraft,
} from "./contact-import-domain";
import {
  buildStyledEmailTemplateBody,
  DEFAULT_ACTION_TOKEN,
  detectedPlaceholders,
  emailTemplateDraftValidation,
  MOCK_REPLACEMENTS,
  parseEmailTemplateEditorDraft,
  renderCampaignEmailPreviewShell,
  renderEditableCampaignBody,
  renderEditablePlaceholders,
  renderEmailTemplatePreviewBody,
  replacePreviewPlaceholders,
  upsertEmailTemplate,
} from "./email-template-domain";
import {
  campaignSaveFailureFromError,
  campaignSendReadinessError,
  normalizeCampaignUrl,
  validateCampaignDraft,
  type CampaignFieldErrors,
  type CampaignFieldName,
  type CampaignSaveFailure,
} from "./campaign-validation";

type TabKey = "campaigns" | "templates";
type CampaignViewKey = "contacts" | "campaigns" | "archive";

const CAMPAIGN_FIELD_ELEMENT_IDS: Array<[CampaignFieldName, string]> = [
  ["name", "campaign-name"],
  ["subject", "campaign-subject"],
  ["body", "campaign-plain-body"],
  ["videoUrl", "campaign-video-url"],
  ["thumbnailUrl", "campaign-thumbnail-url"],
  ["landingUrl", "campaign-landing-url"],
];

function focusFirstCampaignFieldError(fieldErrors: CampaignFieldErrors) {
  const firstInvalidField = CAMPAIGN_FIELD_ELEMENT_IDS.find(([field]) => fieldErrors[field]);
  window.requestAnimationFrame(() => {
    if (firstInvalidField) document.getElementById(firstInvalidField[1])?.focus();
  });
}

function normalizeEmailTab(value: string | null): TabKey {
  return value === "templates" ? "templates" : "campaigns";
}

function normalizeCampaignView(value: string | null): CampaignViewKey {
  return value === "contacts" || value === "archive" ? value : "campaigns";
}

function normalizeCampaignContactTypeFilter(value: string | null): CampaignContactTypeFilter {
  return value === "past_customer" || value === "potential_customer" ? value : "all";
}

type EmailConfirmDialogState = {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "default" | "danger";
  onConfirm: () => void | Promise<void>;
};

export type EmailWorkspaceProps = {
  initialSummary: EmailOpsSummary;
};

export function EmailWorkspace({ initialSummary }: EmailWorkspaceProps) {
  const { get, searchKey, setParam, setParams } = useUrlState();
  const contactImportInputRef = useRef<HTMLInputElement>(null);
  const campaignAssetInputRef = useRef<HTMLInputElement>(null);
  const localTemplateCounterRef = useRef(0);
  const manualContactSubmittingRef = useRef(false);
  const contactFileProcessingRef = useRef(false);
  const contactImportSubmittingRef = useRef(false);
  const campaignAssetPreviewUrlRef = useRef<string | null>(null);
  const campaignSaveSubmittingRef = useRef(false);
  const campaignMembershipSavingRef = useRef<string | null>(null);
  const campaignSendingRef = useRef<string | null>(null);
  const campaignSendIdempotencyKeysRef = useRef(new Map<string, string>());
  const workspaceRefreshInFlightRef = useRef<Promise<void> | null>(null);
  const workspaceRefreshQueuedRef = useRef<Promise<void> | null>(null);
  const rapidRefreshUntilRef = useRef(0);
  const campaignDeletingRef = useRef<string | null>(null);
  const contactSavingRef = useRef<string | null>(null);
  const contactDeletingRef = useRef<string | null>(null);
  const bulkContactActionRef = useRef<null | "activate" | "suppress" | "delete">(null);
  const templateOperationRef = useRef<null | "save" | "create" | "version" | "delete">(null);
  const [activeTab, setActiveTabState] = useState<TabKey>(normalizeEmailTab(get("tab")));
  const [summary, setSummary] = useState<EmailOpsSummary>(initialSummary);
  const [sendCapacity, setSendCapacity] = useState<EmailSendCapacity | null>(null);

  function setActiveTab(tab: TabKey) {
    setActiveTabState(tab);
    setParams(
      {
        tab: tab === "campaigns" ? null : tab,
        view: null,
        modal: null,
        campaignId: null,
      },
      "push",
    );
  }

  useEffect(() => {
    const tab = get("tab");
    const normalizedTab = normalizeEmailTab(tab);
    setActiveTabState(normalizedTab);
    if (tab && tab !== normalizedTab) {
      setParams({ tab: normalizedTab === "campaigns" ? null : normalizedTab, modal: null, campaignId: null }, "replace");
    }
  }, [get, searchKey, setParams]);

  const refreshSummary = useCallback(async () => {
    const fresh = await getEmailOpsSummary({ catalogScope: "active" });
    setSummary(fresh);
    try {
      setSendCapacity(await getEmailSendCapacity());
    } catch {
      setSendCapacity(null);
    }
  }, []);
  const refreshSendCapacity = useCallback(async () => {
    try {
      setSendCapacity(await getEmailSendCapacity());
    } catch {
      setSendCapacity(null);
    }
  }, []);
  const [archivedCampaignRecipients, setArchivedCampaignRecipients] = useState<CampaignRecipientRow[]>([]);
  const refreshArchivedRecipients = useCallback(async () => {
    const archivedSummary = await getEmailOpsSummary({ catalogScope: "archived" });
    setArchivedCampaignRecipients(archivedSummary.campaign.recipients);
  }, []);

  // Template Manager States
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateIdState] = useState<string>(get("templateId") ?? "");
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [templateOperation, setTemplateOperation] = useState<null | "save" | "create" | "version" | "delete">(null);

  function setSelectedTemplateId(templateId: string) {
    setSelectedTemplateIdState(templateId);
    setParam("templateId", templateId || null, "push");
  }

  // Editor fields
  const [editSubject, setEditSubject] = useState("");
  const [editHeading, setEditHeading] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLane, setEditLane] = useState<"transactional" | "campaign">("transactional");
  const [previewCalendlyUrl, setPreviewCalendlyUrl] = useState(MOCK_REPLACEMENTS["{calendly_url}"]);

  // Campaign Manager States
  const [isUploadingCSV, setIsUploadingCSV] = useState(false);
  const [importSheetName, setImportSheetName] = useState<string | null>(null);
  const [importDrafts, setImportDrafts] = useState<CampaignImportDraft[]>([]);
  const [isImportingContacts, setIsImportingContacts] = useState(false);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [isLoadingCampaigns, setIsLoadingCampaigns] = useState(false);
  const [isCreatingCampaign, setIsCreatingCampaign] = useState(false);
  const [showCampaignModal, setShowCampaignModal] = useState(get("modal") === "new-campaign" || get("modal") === "edit-campaign");
  const [editingCampaign, setEditingCampaign] = useState<EmailCampaign | null>(null);
  const [campaignModalHydrationKey, setCampaignModalHydrationKey] = useState<string | null>(null);
  const [campaignView, setCampaignViewState] = useState<CampaignViewKey>(normalizeCampaignView(get("view")));
  const [campaignName, setCampaignName] = useState("Campanie video leadership");
  const [campaignSegment, setCampaignSegment] = useState<CampaignTargetSegment>("potential_customer");
  const [campaignTemplateId, setCampaignTemplateId] = useState("");
  const [campaignSubject, setCampaignSubject] = useState("O idee practică pentru echipa ta, {first_name}");
  const [campaignBody, setCampaignBody] = useState("");
  const [campaignPlainBody, setCampaignPlainBody] = useState("");
  const [campaignVideoUrl, setCampaignVideoUrl] = useState("");
  const [campaignThumbnailUrl, setCampaignThumbnailUrl] = useState("");
  const [campaignLandingUrl, setCampaignLandingUrl] = useState("");
  const [campaignMessage, setCampaignMessage] = useState<string | null>(null);
  const [campaignSaveFailure, setCampaignSaveFailure] = useState<CampaignSaveFailure | null>(null);
  const [campaignFieldErrors, setCampaignFieldErrors] = useState<CampaignFieldErrors>({});
  const pendingCampaignErrorFocusRef = useRef(false);
  const [campaignAssetMessage, setCampaignAssetMessage] = useState<string | null>(null);
  const [pendingCampaignAssetCleanup, setPendingCampaignAssetCleanup] = useState<string | null>(null);
  const [isRetryingCampaignAssetCleanup, setIsRetryingCampaignAssetCleanup] = useState(false);
  const [isUploadingCampaignAsset, setIsUploadingCampaignAsset] = useState(false);
  const [pendingCampaignAsset, setPendingCampaignAsset] = useState<File | null>(null);
  const [campaignAssetPreviewUrl, setCampaignAssetPreviewUrl] = useState<string | null>(null);
  const [sendingCampaignId, setSendingCampaignId] = useState<string | null>(null);
  const [sendingCampaignMode, setSendingCampaignMode] = useState<CampaignSendMode | null>(null);
  const [sendingCampaignRecipientId, setSendingCampaignRecipientId] = useState<string | null>(null);
  const [deletingCampaignId, setDeletingCampaignId] = useState<string | null>(null);
  const [campaignSendResults, setCampaignSendResults] = useState<Record<string, CampaignSendResponse>>({});
  const [campaignMemberships, setCampaignMemberships] = useState<Record<string, string[]>>({});
  const [campaignMembershipDeliveries, setCampaignMembershipDeliveries] = useState<Record<string, Record<string, CampaignDeliveryState>>>({});
  const [campaignMembershipSearches, setCampaignMembershipSearches] = useState<Record<string, string>>({});
  const [campaignMembershipTypeFilters, setCampaignMembershipTypeFilters] = useState<Record<string, CampaignContactTypeFilter>>({});
  const [campaignMembershipCompanySelections, setCampaignMembershipCompanySelections] = useState<Record<string, string>>({});
  const [campaignMembershipErrors, setCampaignMembershipErrors] = useState<Record<string, string>>({});
  const [savingCampaignMembershipId, setSavingCampaignMembershipId] = useState<string | null>(null);
  const [openCampaignId, setOpenCampaignId] = useState<string | null>(null);
  const [campaignContactMessage, setCampaignContactMessage] = useState<string | null>(null);
  const [selectedCampaignRecipientIds, setSelectedCampaignRecipientIds] = useState<string[]>([]);
  const [showInactiveCampaignContacts, setShowInactiveCampaignContacts] = useState(false);
  const [campaignContactSearch, setCampaignContactSearch] = useState("");
  const [archiveContactSearch, setArchiveContactSearch] = useState("");
  const [campaignContactTypeFilter, setCampaignContactTypeFilterState] = useState<CampaignContactTypeFilter>(
    normalizeCampaignContactTypeFilter(get("contactType")),
  );
  const [bulkContactAction, setBulkContactAction] = useState<null | "activate" | "suppress" | "delete">(null);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [contactDrafts, setContactDrafts] = useState<Record<string, CampaignContactDraft>>({});
  const [savingContactId, setSavingContactId] = useState<string | null>(null);
  const [deletingContactId, setDeletingContactId] = useState<string | null>(null);
  const [archiveContactAction, setArchiveContactAction] = useState<{
    recipientId: string;
    kind: "restore" | "delete";
  } | null>(null);
  const [rapidRefreshVersion, setRapidRefreshVersion] = useState(0);
  const [emailNoticeMessage, setEmailNoticeMessage] = useState<string | null>(null);
  const [emailConfirmDialog, setEmailConfirmDialog] = useState<EmailConfirmDialogState | null>(null);

  const activeWorkspaceView: EmailWorkspaceView = activeTab === "templates" ? "templates" : campaignView;
  const readyCampaignCount = campaigns.filter((campaign) => campaign.status === "ready").length;

  function setWorkspaceView(view: EmailWorkspaceView) {
    if (view === "templates") {
      setActiveTab("templates");
      return;
    }

    setActiveTabState("campaigns");
    setCampaignViewState(view);
    setParams(
      {
        tab: null,
        view: view === "campaigns" ? null : view,
        modal: null,
        campaignId: null,
      },
      "push",
    );
  }

  function setCampaignContactTypeFilter(value: CampaignContactTypeFilter) {
    setCampaignContactTypeFilterState(value);
    setParam("contactType", value === "all" ? null : value, "replace");
  }

  function clearCampaignFieldError(field: CampaignFieldName) {
    setCampaignFieldErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  const clearPendingCampaignAsset = useCallback(() => {
    if (campaignAssetPreviewUrlRef.current && typeof URL.revokeObjectURL === "function") {
      URL.revokeObjectURL(campaignAssetPreviewUrlRef.current);
    }
    campaignAssetPreviewUrlRef.current = null;
    setCampaignAssetPreviewUrl(null);
    setPendingCampaignAsset(null);
  }, []);

  useEffect(() => () => {
    if (campaignAssetPreviewUrlRef.current && typeof URL.revokeObjectURL === "function") {
      URL.revokeObjectURL(campaignAssetPreviewUrlRef.current);
    }
  }, []);

  useEffect(() => {
    if (!pendingCampaignErrorFocusRef.current || !showCampaignModal || isCreatingCampaign) return;
    pendingCampaignErrorFocusRef.current = false;
    focusFirstCampaignFieldError(campaignFieldErrors);
  }, [campaignFieldErrors, isCreatingCampaign, showCampaignModal]);

  function closeCampaignModal(mode: "push" | "replace" = "push") {
    clearPendingCampaignAsset();
    setShowCampaignModal(false);
    setEditingCampaign(null);
    setCampaignModalHydrationKey(null);
    setParams({ modal: null, campaignId: null }, mode);
  }

  function closeManualAddModal(mode: "push" | "replace" = "push") {
    setShowManualAddModal(false);
    setParam("modal", null, mode);
  }

  const sortedCampaignRecipients = useMemo(
    () =>
      [...summary.campaign.recipients].sort((first, second) =>
        campaignRecipientSortKey(first).localeCompare(campaignRecipientSortKey(second), "ro-RO"),
      ),
    [summary.campaign.recipients],
  );
  const activeCampaignContacts = useMemo(
    () => sortedCampaignRecipients.filter(isCampaignRecipientEffectivelyActive),
    [sortedCampaignRecipients],
  );
  const inactiveCampaignContacts = useMemo(
    () => sortedCampaignRecipients.filter(
      (recipient) => !isCampaignRecipientEffectivelyActive(recipient),
    ),
    [sortedCampaignRecipients],
  );
  const visibleCampaignContacts = useMemo(
    () => {
      const baseContacts = showInactiveCampaignContacts
        ? sortedCampaignRecipients
        : activeCampaignContacts;
      return baseContacts.filter((recipient) => {
        if (campaignContactTypeFilter !== "all" && campaignRecipientSegment(recipient) !== campaignContactTypeFilter) {
          return false;
        }
        return campaignRecipientMatchesSearch(recipient, campaignContactSearch);
      });
    },
    [
      activeCampaignContacts,
      campaignContactSearch,
      campaignContactTypeFilter,
      showInactiveCampaignContacts,
      sortedCampaignRecipients,
    ],
  );
  const visibleArchivedCampaignContacts = useMemo(
    () =>
      [...archivedCampaignRecipients]
        .sort((first, second) =>
          campaignRecipientSortKey(first).localeCompare(campaignRecipientSortKey(second), "ro-RO"),
        )
        .filter((recipient) => campaignRecipientMatchesSearch(recipient, archiveContactSearch)),
    [archiveContactSearch, archivedCampaignRecipients],
  );
  const selectableCampaignRecipientIdSet = useMemo(
    () =>
      new Set(
        visibleCampaignContacts
          .filter((recipient) => recipient.status !== "unsubscribed" && recipient.email.trim())
          .map((recipient) => recipient.id),
      ),
    [visibleCampaignContacts],
  );
  const visibleSelectableCampaignRecipientIds = useMemo(
    () => visibleCampaignContacts
      .filter((recipient) => selectableCampaignRecipientIdSet.has(recipient.id))
      .map((recipient) => recipient.id),
    [selectableCampaignRecipientIdSet, visibleCampaignContacts],
  );
  const visibleSelectedCampaignRecipientIds = useMemo(
    () => selectedCampaignRecipientIds.filter((recipientId) => selectableCampaignRecipientIdSet.has(recipientId)),
    [selectableCampaignRecipientIdSet, selectedCampaignRecipientIds],
  );
  const isSelectedCampaignContactBeingEdited = editingContactId !== null
    && visibleSelectedCampaignRecipientIds.includes(editingContactId);
  const campaignContactsById = useMemo(
    () => new Map(summary.campaign.recipients.map((recipient) => [recipient.id, recipient])),
    [summary.campaign.recipients],
  );
  const visibleContactsAllSelected = visibleSelectableCampaignRecipientIds.length > 0
    && visibleSelectableCampaignRecipientIds.every((recipientId) => selectedCampaignRecipientIds.includes(recipientId));
  const previewReplacements = useMemo<Record<string, string>>(
    () => ({
      ...MOCK_REPLACEMENTS,
      "{calendly_url}": previewCalendlyUrl,
    }),
    [previewCalendlyUrl],
  );
  const campaignPreviewReplacements = useMemo(() => {
    const videoUrl = campaignVideoUrl.trim();
    const landingUrl = campaignLandingUrl.trim() || videoUrl;
    const thumbnailUrl = campaignAssetPreviewUrl || campaignThumbnailUrl.trim();
    return {
      ...previewReplacements,
      "{video_url}": videoUrl || previewReplacements["{video_url}"],
      "{landing_page_url}": landingUrl || previewReplacements["{landing_page_url}"],
      "{thumbnail_url}": thumbnailUrl || previewReplacements["{thumbnail_url}"],
    };
  }, [campaignAssetPreviewUrl, campaignLandingUrl, campaignThumbnailUrl, campaignVideoUrl, previewReplacements]);
  const campaignMediaHasChanges = useMemo(() => {
    if (!editingCampaign) return Boolean(pendingCampaignAsset);
    return (
      Boolean(pendingCampaignAsset)
      ||
      (editingCampaign.video_url ?? "") !== campaignVideoUrl.trim()
      || (editingCampaign.thumbnail_url ?? "") !== campaignThumbnailUrl.trim()
      || (editingCampaign.landing_page_url ?? "") !== campaignLandingUrl.trim()
    );
  }, [campaignLandingUrl, campaignThumbnailUrl, campaignVideoUrl, editingCampaign, pendingCampaignAsset]);

  const campaignTemplates = useMemo(
    () => templates.filter((template) => {
      if (template.lane !== "campaign") return false;
      if (campaignSegment === null) return true;
      const audience = template.audience ?? "";
      if (campaignSegment === "past_customer") return audience.includes("past_customer");
      return audience.includes("potential_customer");
    }),
    [campaignSegment, templates],
  );

  const selectedCampaignTemplate = useMemo(
    () => campaignTemplates.find((template) => template.id === campaignTemplateId) ?? null,
    [campaignTemplateId, campaignTemplates],
  );

  const applyCampaignToModal = useCallback((campaign: EmailCampaign) => {
    clearPendingCampaignAsset();
    setEditingCampaign(campaign);
    setCampaignName(campaign.name);
    setCampaignSegment(campaign.segment);
    setCampaignTemplateId("");
    const editableBody = renderEditableCampaignBody(campaign);
    setCampaignSubject(renderEditablePlaceholders(campaign.subject));
    setCampaignBody(editableBody);
    setCampaignPlainBody(parseEmailTemplateEditorDraft(editableBody, "").body);
    setCampaignVideoUrl(campaign.video_url ?? "");
    setCampaignThumbnailUrl(campaign.thumbnail_url ?? "");
    setCampaignLandingUrl(campaign.landing_page_url ?? "");
    setCampaignFieldErrors({});
    setCampaignSaveFailure(null);
    setCampaignAssetMessage(null);
    setCampaignMessage(null);
  }, [clearPendingCampaignAsset]);

  const resetCampaignModal = useCallback(() => {
    clearPendingCampaignAsset();
    setEditingCampaign(null);
    setCampaignName("Campanie video leadership");
    setCampaignSegment("potential_customer");
    setCampaignTemplateId("");
    setCampaignSubject("O idee practică pentru echipa ta, {first_name}");
    setCampaignBody("");
    setCampaignPlainBody("");
    setCampaignVideoUrl("");
    setCampaignThumbnailUrl("");
    setCampaignLandingUrl("");
    setCampaignFieldErrors({});
    setCampaignSaveFailure(null);
    setCampaignAssetMessage(null);
  }, [clearPendingCampaignAsset]);

  function openCreateCampaignModal() {
    resetCampaignModal();
    setCampaignModalHydrationKey("new");
    setCampaignMessage(null);
    setShowCampaignModal(true);
    setParams({ tab: "campaigns", modal: "new-campaign", campaignId: null }, "push");
  }

  function openEditCampaignModal(campaign: EmailCampaign) {
    applyCampaignToModal(campaign);
    setCampaignModalHydrationKey(`edit:${campaign.id}`);
    setShowCampaignModal(true);
    setParams({ tab: "campaigns", view: "campaigns", modal: "edit-campaign", campaignId: campaign.id }, "push");
  }

  const urlTemplateId = get("templateId") ?? "";
  const urlCampaignView = normalizeCampaignView(get("view"));
  const urlCampaignContactTypeFilter = normalizeCampaignContactTypeFilter(get("contactType"));
  const urlModal = get("modal");
  const urlCampaignId = get("campaignId");
  const isManualAddModalOpen = urlModal === "add-contact";

  useEffect(() => {
    setSelectedTemplateIdState(urlTemplateId);
    setCampaignViewState(urlCampaignView);
    setCampaignContactTypeFilterState(urlCampaignContactTypeFilter);
    setShowManualAddModal(isManualAddModalOpen);

    if (urlModal === "new-campaign") {
      if (campaignModalHydrationKey !== "new") {
        resetCampaignModal();
        setCampaignMessage(null);
        setCampaignModalHydrationKey("new");
      }
      setShowCampaignModal(true);
      return;
    }

    if (urlModal === "edit-campaign") {
      const campaign = urlCampaignId ? campaigns.find((item) => item.id === urlCampaignId) : null;
      if (campaign) {
        const nextHydrationKey = `edit:${campaign.id}`;
        if (campaignModalHydrationKey !== nextHydrationKey) {
          applyCampaignToModal(campaign);
          setCampaignModalHydrationKey(nextHydrationKey);
        }
        setShowCampaignModal(true);
      } else {
        setShowCampaignModal(false);
      }
      return;
    }

    setShowCampaignModal(false);
    setEditingCampaign(null);
    setCampaignModalHydrationKey(null);
  }, [
    applyCampaignToModal,
    campaignModalHydrationKey,
    campaigns,
    isManualAddModalOpen,
    resetCampaignModal,
    searchKey,
    urlCampaignId,
    urlCampaignContactTypeFilter,
    urlCampaignView,
    urlModal,
    urlTemplateId,
  ]);

  // Manual Add State
  const [showManualAddModal, setShowManualAddModal] = useState(get("modal") === "add-contact");
  const [manualEmail, setManualEmail] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualCompany, setManualCompany] = useState("");
  const [manualSegment, setManualSegment] = useState<"past_customer" | "potential_customer">("potential_customer");
  const [isAddingManual, setIsAddingManual] = useState(false);

  const handleAddManualContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualEmail.trim() || manualContactSubmittingRef.current) return;
    manualContactSubmittingRef.current = true;
    setIsAddingManual(true);
    setCampaignContactMessage(null);
    try {
      await bulkCreateCampaignRecipientsOnServer([{
        email: manualEmail.trim(),
        contact_name: manualName.trim() || undefined,
        organization_name: manualCompany.trim() || undefined,
        segment: manualSegment,
      }]);
      setCampaignContactMessage("Contactul a fost adăugat.");
      closeManualAddModal("replace");
      setManualEmail("");
      setManualName("");
      setManualCompany("");
      await refreshWorkspace();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi adăugat.");
    } finally {
      manualContactSubmittingRef.current = false;
      setIsAddingManual(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (contactFileProcessingRef.current) {
      e.target.value = "";
      return;
    }
    contactFileProcessingRef.current = true;
    setIsUploadingCSV(true);
    try {
      const spreadsheet = await readSpreadsheetFile(file, selectCampaignRecipientImportSheetName);
      const sheetName = spreadsheet.sheetName;
      const rows = spreadsheetRowsToObjects(spreadsheet.rows);
      const drafts = buildCampaignRecipientImportDrafts(rows);

      if (drafts.length > 0) {
        const invalidCount = drafts.filter(importDraftHasEmailError).length;
        setImportSheetName(sheetName ?? null);
        setImportDrafts(drafts);
        setCampaignContactMessage(
          `Previzualizare ${drafts.length} contacte din sheet-ul ${sheetName ?? "selectat"}.${invalidCount > 0 ? ` ${invalidCount} emailuri trebuie corectate.` : ""}`,
        );
      } else {
        setCampaignContactMessage("Fișierul nu conține contacte de importat.");
      }
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Fișierul nu a putut fi procesat.");
    } finally {
      contactFileProcessingRef.current = false;
      setIsUploadingCSV(false);
      e.target.value = "";
    }
  };

  const updateImportDraft = <K extends keyof CampaignImportDraft>(
    rowId: string,
    field: K,
    value: CampaignImportDraft[K],
  ) => {
    setImportDrafts((previousDrafts) =>
      previousDrafts.map((draft) =>
        draft.id === rowId
          ? {
              ...draft,
              [field]: value,
              send: field === "email" && !isValidImportEmail(String(value).trim()) ? false : draft.send,
            }
          : draft,
      ),
    );
  };

  const invalidImportDraftCount = importDrafts.filter(importDraftHasEmailError).length;
  const activeImportDraftCount = importDrafts.filter((draft) => draft.send).length;
  const duplicateImportDraftEmailCount = useMemo(
    () => uniqueCampaignImportDrafts(importDrafts).duplicateEmailCount,
    [importDrafts],
  );

  const confirmCampaignRecipientImport = async () => {
    if (contactImportSubmittingRef.current) return;
    if (invalidImportDraftCount > 0) {
      setCampaignContactMessage("Corectează emailurile invalide înainte de import.");
      return;
    }
    contactImportSubmittingRef.current = true;
    setIsImportingContacts(true);
    try {
      const { duplicateEmailCount, uniqueDrafts } = uniqueCampaignImportDrafts(importDrafts);
      const activeUniqueDraftCount = uniqueDrafts.filter((draft) => draft.send).length;
      const result = await bulkCreateCampaignRecipientsOnServer(uniqueDrafts.map(campaignImportDraftToRecipient));
      const savedCount = typeof result?.count === "number" ? result.count : uniqueDrafts.length;
      const createdCount = typeof result?.created === "number" ? result.created : null;
      const updatedCount = typeof result?.updated === "number" ? result.updated : null;
      const metricCopy = createdCount !== null && updatedCount !== null
        ? `${createdCount} noi, ${updatedCount} actualizate`
        : `${savedCount} salvate`;
      setCampaignContactMessage(
        `S-au importat ${savedCount} contacte (${metricCopy}): ${activeUniqueDraftCount} active, ${uniqueDrafts.length - activeUniqueDraftCount} cu trimiterea oprită.${duplicateEmailCount > 0 ? ` ${duplicateEmailCount} duplicate cu același email au fost consolidate folosind ultima apariție.` : ""}`,
      );
      setImportDrafts([]);
      setImportSheetName(null);
      await refreshWorkspace();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactele nu au putut fi importate.");
    } finally {
      contactImportSubmittingRef.current = false;
      setIsImportingContacts(false);
    }
  };

  const loadCampaigns = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setIsLoadingCampaigns(true);
    try {
      const nextCampaigns = await listCampaignsOnServer();
      setCampaigns(nextCampaigns);
      const membershipResults = await Promise.allSettled(
        nextCampaigns.map(async (campaign) => {
          const recipients = await listCampaignRecipientMembershipOnServer(campaign.id);
          return [
            campaign.id,
            recipients.map((recipient) => recipient.id),
            Object.fromEntries(
              recipients.map((recipient) => [
                recipient.id,
                recipient.campaignDelivery ?? "not_sent",
              ]),
            ) as Record<string, CampaignDeliveryState>,
          ] as const;
        }),
      );
      const membershipEntries = membershipResults
        .filter((result): result is PromiseFulfilledResult<readonly [string, string[], Record<string, CampaignDeliveryState>]> => result.status === "fulfilled")
        .map((result) => result.value);
      const membershipBeingSaved = campaignMembershipSavingRef.current;
      setCampaignMemberships((currentMemberships) => ({
        ...Object.fromEntries(
          membershipEntries.map(([campaignId, recipientIds]) => [campaignId, recipientIds]),
        ),
        ...(membershipBeingSaved && currentMemberships[membershipBeingSaved]
          ? { [membershipBeingSaved]: currentMemberships[membershipBeingSaved] }
          : {}),
      }));
      setCampaignMembershipDeliveries((currentDeliveries) => ({
        ...Object.fromEntries(
          membershipEntries.map(([campaignId, , deliveries]) => [campaignId, deliveries]),
        ),
        ...(membershipBeingSaved && currentDeliveries[membershipBeingSaved]
          ? { [membershipBeingSaved]: currentDeliveries[membershipBeingSaved] }
          : {}),
      }));
      const failedCount = membershipResults.length - membershipEntries.length;
      if (failedCount > 0) {
        setCampaignMessage(`${failedCount} liste de destinatari nu au putut fi încărcate. Reîncarcă pagina înainte de trimitere.`);
      }
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Campaniile nu au putut fi încărcate.");
    } finally {
      if (!silent) setIsLoadingCampaigns(false);
    }
  }, []);

  useEffect(() => {
    void loadCampaigns();
    void refreshSendCapacity();
    void refreshArchivedRecipients();
  }, [loadCampaigns, refreshArchivedRecipients, refreshSendCapacity]);

  const refreshWorkspace = useCallback((): Promise<void> => {
    const startRefresh = () => {
      const refresh = (async () => {
        await Promise.allSettled([
          refreshSummary(),
          refreshArchivedRecipients(),
          loadCampaigns({ silent: true }),
        ]);
      })();
      workspaceRefreshInFlightRef.current = refresh;
      void refresh.finally(() => {
        if (workspaceRefreshInFlightRef.current === refresh) {
          workspaceRefreshInFlightRef.current = null;
        }
      });
      return refresh;
    };

    const inFlight = workspaceRefreshInFlightRef.current;
    if (!inFlight) return startRefresh();
    let queued = workspaceRefreshQueuedRef.current;
    if (!queued) {
      queued = inFlight.then(startRefresh, startRefresh);
      workspaceRefreshQueuedRef.current = queued;
      void queued.finally(() => {
        if (workspaceRefreshQueuedRef.current === queued) {
          workspaceRefreshQueuedRef.current = null;
        }
      });
    }
    return queued;
  }, [loadCampaigns, refreshArchivedRecipients, refreshSummary]);

  const startRapidRefresh = useCallback(() => {
    rapidRefreshUntilRef.current = Date.now() + 60_000;
    setRapidRefreshVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void refreshWorkspace();
    };
    const interval = window.setInterval(refreshWhenVisible, 10_000);
    window.addEventListener("focus", refreshWhenVisible);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshWhenVisible);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [refreshWorkspace]);

  useEffect(() => {
    if (rapidRefreshVersion === 0) return;
    let interval = 0;
    const poll = () => {
      if (Date.now() >= rapidRefreshUntilRef.current) {
        window.clearInterval(interval);
        return;
      }
      if (document.visibilityState === "visible") void refreshWorkspace();
    };
    interval = window.setInterval(poll, 2_000);
    return () => window.clearInterval(interval);
  }, [rapidRefreshVersion, refreshWorkspace]);

  const handleCampaignAssetUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    clearPendingCampaignAsset();
    const previewUrl = typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null;
    campaignAssetPreviewUrlRef.current = previewUrl;
    setCampaignAssetPreviewUrl(previewUrl);
    setPendingCampaignAsset(file);
    setCampaignAssetMessage(null);
    clearCampaignFieldError("thumbnailUrl");
    setCampaignAssetMessage(`${file.name} este pregătit pentru salvare.`);
    event.target.value = "";
  };

  const handleSaveCampaign = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (campaignSaveSubmittingRef.current) return;
    const templateBody = campaignBody || selectedCampaignTemplate?.body || "";
    const templateText = htmlToPlainText(templateBody);
    const thumbnailForValidation = pendingCampaignAsset
      ? "https://pending.codrut.local/campaign-image"
      : campaignThumbnailUrl;
    const draft = {
      name: campaignName,
      segment: campaignSegment,
      subject: campaignSubject,
      htmlBody: templateBody,
      textBody: templateText,
      videoUrl: campaignVideoUrl,
      thumbnailUrl: thumbnailForValidation,
      landingUrl: campaignLandingUrl,
    };
    const fieldErrors = validateCampaignDraft(draft);

    if (Object.keys(fieldErrors).length > 0) {
      pendingCampaignErrorFocusRef.current = true;
      setCampaignFieldErrors(fieldErrors);
      setCampaignSaveFailure(null);
      setCampaignMessage(null);
      return;
    }

    setCampaignFieldErrors({});
    campaignSaveSubmittingRef.current = true;
    setIsCreatingCampaign(true);
    setCampaignMessage(null);
    setCampaignSaveFailure(null);
    let uploadedAsset: Awaited<ReturnType<typeof uploadCampaignAssetOnServer>> | null = null;
    let campaignPersisted = false;
    try {
      let effectiveThumbnailUrl = campaignThumbnailUrl;
      if (pendingCampaignAsset) {
        setIsUploadingCampaignAsset(true);
        setCampaignAssetMessage("Încărcăm imaginea...");
        uploadedAsset = await uploadCampaignAssetOnServer(pendingCampaignAsset);
        effectiveThumbnailUrl = uploadedAsset.url;
      }

      const hasIncompleteVideoDraft = Boolean(
        campaignVideoUrl.trim() && !effectiveThumbnailUrl.trim(),
      );
      const basePayload = buildVideoCampaignCreatePayload({
        ...draft,
        thumbnailUrl: effectiveThumbnailUrl,
        videoUrl: hasIncompleteVideoDraft ? "" : campaignVideoUrl,
      });
      const payload: CampaignCreate | null = basePayload
        ? {
            ...basePayload,
            video_url: normalizeCampaignUrl(campaignVideoUrl),
            thumbnail_url: normalizeCampaignUrl(effectiveThumbnailUrl),
            landing_page_url: normalizeCampaignUrl(campaignLandingUrl),
          }
        : null;

      if (!payload) {
        throw new CampaignPersistenceError(
          "Campania nu a putut fi pregătită. Verifică datele introduse.",
          422,
        );
      }

      const previousAssetFileName = campaignAssetFileNameFromUrl(editingCampaign?.thumbnail_url);
      let savedCampaign: EmailCampaign;
      if (editingCampaign) {
        savedCampaign = await updateCampaignOnServer(editingCampaign.id, {
          ...payload,
          video_url: campaignVideoUrl.trim() ? payload.video_url : null,
          thumbnail_url: effectiveThumbnailUrl.trim() ? payload.thumbnail_url : null,
          landing_page_url: campaignLandingUrl.trim() ? payload.landing_page_url : null,
          status: hasIncompleteVideoDraft ? "draft" : "ready",
        });
        setCampaignMessage("Campania a fost actualizată.");
        setOpenCampaignId(savedCampaign.id);
      } else {
        savedCampaign = await createCampaignOnServer(payload);
        setCampaignMessage(`Campania „${savedCampaign.name}” a fost creată.`);
        setOpenCampaignId(savedCampaign.id);
      }
      campaignPersisted = true;

      const savedAssetFileName = campaignAssetFileNameFromUrl(savedCampaign.thumbnail_url);
      if (previousAssetFileName && previousAssetFileName !== savedAssetFileName) {
        try {
          await deleteCampaignAssetOnServer(previousAssetFileName);
        } catch {
          setPendingCampaignAssetCleanup(previousAssetFileName);
          setCampaignAssetMessage(
            "Campania a fost salvată, dar imaginea înlocuită nu a putut fi eliminată. Reîncearcă.",
          );
        }
      }

      clearPendingCampaignAsset();
      setCampaignThumbnailUrl(savedCampaign.thumbnail_url ?? "");
      setCampaignAssetMessage(null);
      setCampaignViewState("campaigns");
      setShowCampaignModal(false);
      setEditingCampaign(null);
      setCampaignModalHydrationKey(null);
      setParams({ tab: "campaigns", view: "campaigns", modal: null, campaignId: null }, "replace");
      await refreshWorkspace();
    } catch (error) {
      const shouldDeleteUploadedAsset = Boolean(
        uploadedAsset && !campaignPersisted && error instanceof CampaignPersistenceError && error.status,
      );
      let uploadedAssetWasDeleted = false;
      if (shouldDeleteUploadedAsset && uploadedAsset) {
        try {
          await deleteCampaignAssetOnServer(uploadedAsset.file_name);
          uploadedAssetWasDeleted = true;
        } catch {
          setPendingCampaignAssetCleanup(uploadedAsset.file_name);
          setCampaignAssetMessage(
            "Campania nu a fost salvată, iar imaginea încărcată nu a putut fi eliminată. Reîncearcă.",
          );
        }
      } else if (uploadedAsset && !campaignPersisted) {
        setCampaignThumbnailUrl(uploadedAsset.url);
        clearPendingCampaignAsset();
      }
      const saveFailure = campaignSaveFailureFromError(error, draft);
      setCampaignFieldErrors(saveFailure.fieldErrors);
      setCampaignSaveFailure(saveFailure);
      setCampaignMessage(null);
      if (pendingCampaignAsset && uploadedAssetWasDeleted) {
        setCampaignAssetMessage(`${pendingCampaignAsset.name} rămâne selectată pentru următoarea încercare.`);
      }
      if (Object.keys(saveFailure.fieldErrors).length > 0) {
        pendingCampaignErrorFocusRef.current = true;
      }
    } finally {
      campaignSaveSubmittingRef.current = false;
      setIsCreatingCampaign(false);
      setIsUploadingCampaignAsset(false);
    }
  };

  const retryCampaignAssetCleanup = async () => {
    if (!pendingCampaignAssetCleanup || isRetryingCampaignAssetCleanup) return;
    setIsRetryingCampaignAssetCleanup(true);
    try {
      await deleteCampaignAssetOnServer(pendingCampaignAssetCleanup);
      setPendingCampaignAssetCleanup(null);
      setCampaignAssetMessage(null);
      setCampaignMessage("Imaginea rămasă a fost eliminată.");
    } catch {
      setCampaignAssetMessage("Imaginea nu a putut fi eliminată. Reîncearcă.");
    } finally {
      setIsRetryingCampaignAssetCleanup(false);
    }
  };

  const startEditingContact = (recipient: CampaignRecipientRow) => {
    setEditingContactId(recipient.id);
    setCampaignContactMessage(null);
    setContactDrafts((drafts) => ({
      ...drafts,
      [recipient.id]: drafts[recipient.id] ?? campaignRecipientDraft(recipient),
    }));
  };

  const updateContactDraft = <Field extends keyof CampaignContactDraft>(
    recipientId: string,
    field: Field,
    value: CampaignContactDraft[Field],
  ) => {
    setContactDrafts((drafts) => ({
      ...drafts,
      [recipientId]: {
        ...(drafts[recipientId] ?? {
          email: "",
          contact_name: "",
          organization_name: "",
          segment: "potential_customer",
          status: "active",
        }),
        [field]: value,
      },
    }));
  };

  const cancelEditingContact = (recipientId: string) => {
    setEditingContactId(null);
    setContactDrafts((drafts) => {
      const nextDrafts = { ...drafts };
      delete nextDrafts[recipientId];
      return nextDrafts;
    });
  };

  const saveContact = async (recipient: CampaignRecipientRow) => {
    if (contactSavingRef.current || contactDeletingRef.current || bulkContactActionRef.current) return;

    const draft = contactDrafts[recipient.id] ?? campaignRecipientDraft(recipient);
    if (draft.status === "active" && !draft.email.trim()) {
      setCampaignContactMessage("Adaugă email înainte să activezi contactul.");
      return;
    }
    if (
      recipient.status === "suppressed"
      && draft.status === "active"
      && recipient.activationAllowed !== true
    ) {
      setCampaignContactMessage(
        "Corectează și salvează adresa respinsă înainte să activezi din nou contactul.",
      );
      return;
    }

    contactSavingRef.current = recipient.id;
    setSavingContactId(recipient.id);
    setCampaignContactMessage(null);
    try {
      if (recipient.status === "unsubscribed" && draft.status !== "unsubscribed") {
        setCampaignContactMessage("Contactul s-a dezabonat. Statusul nu poate fi schimbat din listă.");
        return;
      }

      await updateCampaignRecipientOnServer(recipient.id, {
        email: draft.email.trim(),
        contact_name: draft.contact_name.trim(),
        organization_name: draft.organization_name.trim(),
        segment: draft.segment,
        status: draft.status,
      });
      const nameParts = splitContactName(draft.contact_name);
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.map((currentRecipient) =>
            currentRecipient.id === recipient.id
              ? {
                  ...currentRecipient,
                  email: draft.email.trim(),
                  company: draft.organization_name.trim() || "Companie necompletată",
                  firstName: nameParts.firstName,
                  lastName: nameParts.lastName,
                  clientType: draft.segment === "past_customer" ? "tip_1" : "tip_2",
                  status: draft.status === "unsubscribed"
                    ? "unsubscribed"
                    : draft.status === "suppressed"
                    ? "suppressed"
                    : draft.contact_name.trim()
                    ? "ready"
                    : "needs_contact_name",
                }
              : currentRecipient,
          ),
        },
      }));
      setCampaignContactMessage("Contactul a fost actualizat.");
      cancelEditingContact(recipient.id);
      await refreshWorkspace();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi actualizat.");
    } finally {
      contactSavingRef.current = null;
      setSavingContactId(null);
    }
  };

  const deleteContact = (recipient: CampaignRecipientRow) => {
    setEmailConfirmDialog({
      title: "Arhivezi contactul?",
      description: `Contactul ${recipient.email} va ieși imediat din liste și campanii. Îl poți restaura din Arhivă.`,
      confirmLabel: "Arhivează",
      tone: "danger",
      onConfirm: async () => {
        if (contactDeletingRef.current || contactSavingRef.current || bulkContactActionRef.current) return;

        contactDeletingRef.current = recipient.id;
        setDeletingContactId(recipient.id);
        setCampaignContactMessage(null);
        try {
          const result = await archiveCampaignRecipientOnServer(recipient.id);
          setCampaignContactMessage(
            result.in_flight > 0
              ? `Contactul a fost arhivat. ${result.in_flight} ${result.in_flight === 1 ? "trimitere era deja în curs și nu mai putea fi oprită" : "trimiteri erau deja în curs și nu mai puteau fi oprite"}.`
              : "Contactul a fost arhivat.",
          );
          if (editingContactId === recipient.id) {
            cancelEditingContact(recipient.id);
          }
          await refreshWorkspace();
        } catch (error) {
          setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi arhivat.");
        } finally {
          contactDeletingRef.current = null;
          setDeletingContactId(null);
        }
      },
    });
  };

  const toggleSelectedCampaignRecipient = (recipientId: string) => {
    if (!selectableCampaignRecipientIdSet.has(recipientId)) return;
    setSelectedCampaignRecipientIds((currentIds) =>
      currentIds.includes(recipientId)
        ? currentIds.filter((id) => id !== recipientId)
        : [...currentIds, recipientId],
    );
  };

  const toggleAllVisibleCampaignRecipients = () => {
    setSelectedCampaignRecipientIds((currentIds) => {
      const currentSet = new Set(currentIds);
      if (visibleContactsAllSelected) {
        return currentIds.filter((recipientId) => !visibleSelectableCampaignRecipientIds.includes(recipientId));
      }
      for (const recipientId of visibleSelectableCampaignRecipientIds) {
        currentSet.add(recipientId);
      }
      return Array.from(currentSet);
    });
  };

  const toggleInactiveCampaignContacts = () => {
    setShowInactiveCampaignContacts((current) => {
      if (current) {
        const inactiveIds = new Set(inactiveCampaignContacts.map((recipient) => recipient.id));
        setSelectedCampaignRecipientIds((currentIds) =>
          currentIds.filter((recipientId) => !inactiveIds.has(recipientId)),
        );
      }
      return !current;
    });
  };

  const updateSelectedCampaignContactsStatus = async (nextStatus: "active" | "suppressed") => {
    if (bulkContactActionRef.current || contactSavingRef.current || contactDeletingRef.current) return;

    if (visibleSelectedCampaignRecipientIds.length === 0) {
      setCampaignContactMessage("Selectează cel puțin un contact.");
      return;
    }
    if (isSelectedCampaignContactBeingEdited) {
      setCampaignContactMessage("Salvează sau anulează editarea înainte de operațiuni în masă.");
      return;
    }
    const selectedContacts = summary.campaign.recipients.filter((recipient) =>
      visibleSelectedCampaignRecipientIds.includes(recipient.id),
    );
    const contactsToUpdate = selectedContacts.filter((recipient) => {
      if (recipient.status === "unsubscribed") return false;
      if (nextStatus === "active" && recipient.status === "suppressed") return false;
      const isActive = isCampaignRecipientEffectivelyActive(recipient);
      return nextStatus === "active" ? !isActive : isActive;
    });
    if (contactsToUpdate.length === 0) {
      setCampaignContactMessage(
        nextStatus === "active"
          ? "Adresele respinse se activează individual, după ce corectezi adresa de email."
          : "Trimiterea este deja oprită pentru contactele selectate.",
      );
      return;
    }

    bulkContactActionRef.current = nextStatus === "active" ? "activate" : "suppress";
    setBulkContactAction(nextStatus === "active" ? "activate" : "suppress");
    setCampaignContactMessage(null);
    try {
      const outcomes = await Promise.allSettled(
        contactsToUpdate.map((recipient) =>
          updateCampaignRecipientOnServer(recipient.id, { status: nextStatus }),
        ),
      );
      const successfulIds = new Set(
        contactsToUpdate
          .filter((_recipient, index) => outcomes[index]?.status === "fulfilled")
          .map((recipient) => recipient.id),
      );
      const failedIds = contactsToUpdate
        .filter((_recipient, index) => outcomes[index]?.status === "rejected")
        .map((recipient) => recipient.id);
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.map((recipient) =>
            successfulIds.has(recipient.id)
              ? {
                  ...recipient,
                  status: nextStatus === "suppressed"
                    ? "suppressed"
                    : campaignRecipientName(recipient)
                    ? "ready"
                    : "needs_contact_name",
                }
              : recipient,
          ),
        },
      }));
      setSelectedCampaignRecipientIds(failedIds);
      try {
        await refreshWorkspace();
      } catch {
        // The reconciled local state remains visible; a route reload can retry the read.
      }
      if (failedIds.length > 0) {
        setCampaignContactMessage(
          `${successfulIds.size} reușite, ${failedIds.length} eșuate. Contactele eșuate au rămas selectate pentru reîncercare.`,
        );
      } else {
        setCampaignContactMessage(
          nextStatus === "active"
            ? `${successfulIds.size} contacte au fost activate.`
            : `Trimiterea a fost oprită pentru ${successfulIds.size} contacte.`,
        );
      }
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Operațiunea pe contacte nu a putut fi finalizată.");
    } finally {
      bulkContactActionRef.current = null;
      setBulkContactAction(null);
    }
  };

  const deleteSelectedCampaignContacts = async () => {
    if (bulkContactActionRef.current || contactSavingRef.current || contactDeletingRef.current) return;

    if (visibleSelectedCampaignRecipientIds.length === 0) {
      setCampaignContactMessage("Selectează cel puțin un contact.");
      return;
    }
    if (isSelectedCampaignContactBeingEdited) {
      setCampaignContactMessage("Salvează sau anulează editarea înainte de arhivarea în masă.");
      return;
    }
    const recipientIdsToArchive = [...visibleSelectedCampaignRecipientIds];
    setEmailConfirmDialog({
      title: "Arhivezi contactele selectate?",
      description: `${recipientIdsToArchive.length} contacte vor ieși imediat din liste și campanii. Le poți restaura din Arhivă.`,
      confirmLabel: "Arhivează",
      tone: "danger",
      onConfirm: async () => {
        if (bulkContactActionRef.current || contactSavingRef.current || contactDeletingRef.current) return;

        bulkContactActionRef.current = "delete";
        setBulkContactAction("delete");
        setCampaignContactMessage(null);
        try {
          const outcomes = await Promise.allSettled(
            recipientIdsToArchive.map((recipientId) => archiveCampaignRecipientOnServer(recipientId)),
          );
          const archivedIds = new Set(
            recipientIdsToArchive.filter((_recipientId, index) => outcomes[index]?.status === "fulfilled"),
          );
          const failedIds = recipientIdsToArchive.filter(
            (_recipientId, index) => outcomes[index]?.status === "rejected",
          );
          setSelectedCampaignRecipientIds(failedIds);
          await refreshWorkspace();
          setCampaignContactMessage(
            failedIds.length > 0
              ? `${archivedIds.size} arhivate, ${failedIds.length} eșuate. Contactele eșuate au rămas selectate pentru reîncercare.`
              : `${archivedIds.size} contacte au fost arhivate.`,
          );
        } catch (error) {
          setCampaignContactMessage(error instanceof Error ? error.message : "Contactele selectate nu au putut fi arhivate.");
        } finally {
          bulkContactActionRef.current = null;
          setBulkContactAction(null);
        }
      },
    });
  };

  const restoreArchivedContact = async (recipient: CampaignRecipientRow) => {
    if (contactDeletingRef.current) return;
    contactDeletingRef.current = recipient.id;
    setArchiveContactAction({ recipientId: recipient.id, kind: "restore" });
    setCampaignContactMessage(null);
    try {
      const restored = await restoreCampaignRecipientOnServer(recipient.id);
      setCampaignContactMessage(
        restored.status === "suppressed"
          ? "Contactul a fost restaurat, dar adresa respinsă rămâne blocată până când o corectezi și o activezi explicit."
          : restored.status === "unsubscribed"
            ? "Contactul a fost restaurat, dar rămâne dezabonat și nu va primi campanii."
            : "Contactul a fost restaurat.",
      );
      await refreshWorkspace();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi restaurat.");
    } finally {
      contactDeletingRef.current = null;
      setArchiveContactAction(null);
    }
  };

  const permanentlyDeleteArchivedContact = (recipient: CampaignRecipientRow) => {
    if (contactDeletingRef.current) return;
    const contactName = campaignRecipientName(recipient) || recipient.email;
    setEmailConfirmDialog({
      title: "Ștergi definitiv contactul?",
      description:
        `${contactName} nu va mai putea fi restaurat. Ștergem datele de contact și legăturile cu ` +
        "campaniile. Păstrăm totalurile fără datele contactului și o amprentă protejată care " +
        "împiedică retrimiterea către o adresă respinsă ori dezabonată.",
      confirmLabel: "Șterge definitiv",
      tone: "danger",
      onConfirm: async () => {
        if (contactDeletingRef.current) return;
        contactDeletingRef.current = recipient.id;
        setArchiveContactAction({ recipientId: recipient.id, kind: "delete" });
        setCampaignContactMessage(null);
        try {
          await permanentlyDeleteCampaignRecipientOnServer(recipient.id);
          await refreshWorkspace();
          setCampaignContactMessage("Contactul a fost șters definitiv.");
        } catch (error) {
          setCampaignContactMessage(
            error instanceof Error ? error.message : "Contactul nu a putut fi șters definitiv.",
          );
        } finally {
          contactDeletingRef.current = null;
          setArchiveContactAction(null);
        }
      },
    });
  };

  const campaignEligibleRecipients = () =>
    summary.campaign.recipients.filter((recipient) =>
      isCampaignRecipientEffectivelyActive(recipient)
      && recipient.email.trim()
    );

  const visibleCampaignEligibleRecipients = (campaign: EmailCampaign) => {
    const search = campaignMembershipSearches[campaign.id] ?? "";
    const typeFilter = campaignMembershipTypeFilters[campaign.id] ?? "all";
    const companyKey = campaignMembershipCompanySelections[campaign.id] ?? "";
    return campaignEligibleRecipients().filter((recipient) =>
      campaignRecipientMatchesSearch(recipient, search)
      && (typeFilter === "all" || campaignRecipientSegment(recipient) === typeFilter)
      && (!companyKey || campaignRecipientCompanyKey(recipient) === companyKey),
    );
  };

  const activeCampaignMembershipIds = (campaign: EmailCampaign) =>
    (campaignMemberships[campaign.id] ?? []).filter((recipientId) => {
      const recipient = campaignContactsById.get(recipientId);
      return Boolean(
        recipient
        && isCampaignRecipientEffectivelyActive(recipient)
        && recipient.email.trim(),
      );
    });

  const campaignRecipientDelivery = (
    campaign: EmailCampaign,
    recipientId: string,
  ): CampaignDeliveryState =>
    campaignMembershipDeliveries[campaign.id]?.[recipientId] ?? "not_sent";

  const campaignDeliveryIsLocked = (delivery: CampaignDeliveryState) =>
    delivery === "sent" || delivery === "queued";

  const sendableCampaignMembershipIds = (campaign: EmailCampaign) =>
    activeCampaignMembershipIds(campaign).filter(
      (recipientId) => !campaignDeliveryIsLocked(campaignRecipientDelivery(campaign, recipientId)),
    );

  const persistCampaignMembership = async (
    campaign: EmailCampaign,
    nextMemberIds: string[],
  ) => {
    if (campaignMembershipSavingRef.current === campaign.id) return;
    campaignMembershipSavingRef.current = campaign.id;
    const uniqueNextMemberIds = Array.from(new Set(nextMemberIds));
    const previousMemberIds = campaignMemberships[campaign.id] ?? [];
    const previousDeliveries = campaignMembershipDeliveries[campaign.id] ?? {};

    setCampaignMemberships((currentMemberships) => ({
      ...currentMemberships,
      [campaign.id]: uniqueNextMemberIds,
    }));
    setSavingCampaignMembershipId(campaign.id);
    setCampaignMembershipErrors((current) => {
      const next = { ...current };
      delete next[campaign.id];
      return next;
    });

    try {
      const savedRows = await replaceCampaignRecipientMembershipOnServer(campaign.id, uniqueNextMemberIds);
      setCampaignMemberships((currentMemberships) => ({
        ...currentMemberships,
        [campaign.id]: savedRows.map((recipient) => recipient.id),
      }));
      setCampaignMembershipDeliveries((currentDeliveries) => ({
        ...currentDeliveries,
        [campaign.id]: Object.fromEntries(
          savedRows.map((recipient) => [
            recipient.id,
            recipient.campaignDelivery ?? "not_sent",
          ]),
        ) as Record<string, CampaignDeliveryState>,
      }));
      await refreshWorkspace();
    } catch (error) {
      setCampaignMemberships((currentMemberships) => ({
        ...currentMemberships,
        [campaign.id]: previousMemberIds,
      }));
      setCampaignMembershipDeliveries((currentDeliveries) => ({
        ...currentDeliveries,
        [campaign.id]: previousDeliveries,
      }));
      setCampaignMembershipErrors((current) => ({
        ...current,
        [campaign.id]: error instanceof Error ? error.message : "Lista campaniei nu a putut fi salvată.",
      }));
    } finally {
      campaignMembershipSavingRef.current = null;
      setSavingCampaignMembershipId(null);
    }
  };

  const toggleCampaignMembershipRecipient = async (campaign: EmailCampaign, recipientId: string) => {
    const eligibleIds = new Set(campaignEligibleRecipients().map((recipient) => recipient.id));
    if (!eligibleIds.has(recipientId)) return;
    if (campaignDeliveryIsLocked(campaignRecipientDelivery(campaign, recipientId))) return;
    const currentIds = activeCampaignMembershipIds(campaign);
    const nextIds = currentIds.includes(recipientId)
      ? currentIds.filter((id) => id !== recipientId)
      : [...currentIds, recipientId];
    await persistCampaignMembership(campaign, nextIds);
  };

  const toggleCampaignMembershipCompany = (
    campaign: EmailCampaign,
    companyKey: string,
    mode: "select" | "deselect",
  ) => {
    const companyRecipientIds = campaignEligibleRecipients()
      .filter((recipient) => campaignRecipientCompanyKey(recipient) === companyKey)
      .map((recipient) => recipient.id);
    if (companyRecipientIds.length === 0) return;

    const currentIds = activeCampaignMembershipIds(campaign);
    if (mode === "deselect") {
      const removableCompanyRecipientIds = new Set(
        companyRecipientIds.filter(
          (recipientId) => !campaignDeliveryIsLocked(campaignRecipientDelivery(campaign, recipientId)),
        ),
      );
      void persistCampaignMembership(
        campaign,
        currentIds.filter((recipientId) => !removableCompanyRecipientIds.has(recipientId)),
      );
      return;
    }

    const nextIds = new Set(currentIds);
    for (const recipientId of companyRecipientIds) {
      nextIds.add(recipientId);
    }
    void persistCampaignMembership(campaign, Array.from(nextIds));
  };

  const handleSendCampaign = async (
    campaign: EmailCampaign,
    mode: CampaignSendMode = "new",
  ) => {
    const readinessError = campaignSendReadinessError(campaign);
    if (readinessError) {
      setCampaignMessage(readinessError);
      return;
    }
    const selectedRecipientIds = mode === "selected" ? sendableCampaignMembershipIds(campaign) : undefined;
    const selectedRecipientCount = selectedRecipientIds?.length ?? 0;
    const plannedRecipientCount = mode === "selected"
      ? selectedRecipientCount
      : activeCampaignMembershipIds(campaign).length;
    if (mode === "selected" && selectedRecipientCount === 0) {
      setCampaignMessage("Lista campaniei nu are destinatari netrimiși disponibili.");
      return;
    }
    setEmailConfirmDialog({
      title: "Trimiți campania?",
      description: mode === "selected"
        ? `Campania „${campaign.name}” va fi trimisă către ${selectedRecipientCount} ${
            selectedRecipientCount === 1 ? "destinatar netrimis" : "destinatari netrimiși"
          } din lista campaniei.`
        : mode === "all"
        ? `Campania „${campaign.name}” va fi trimisă către toți destinatarii salvați ai campaniei, inclusiv cei care au mai primit-o.`
        : `Campania „${campaign.name}” va fi trimisă doar către destinatarii salvați care nu au primit-o încă.`,
      confirmLabel: "Trimite",
      onConfirm: async () => {
        if (campaignSendingRef.current) return;
        campaignSendingRef.current = campaign.id;
        setSendingCampaignId(campaign.id);
        setSendingCampaignMode(mode);
        setCampaignMessage(null);
        try {
          const currentCapacity = await getEmailSendCapacity();
          setSendCapacity(currentCapacity);
          if (plannedRecipientCount > currentCapacity.remaining_today) {
            throw new Error(
              `Mai sunt disponibile ${currentCapacity.remaining_today} emailuri astăzi. Redu lista înainte de trimitere.`,
            );
          }
          if (mode === "selected" && selectedRecipientIds) {
            const savedRows = await replaceCampaignRecipientMembershipOnServer(
              campaign.id,
              activeCampaignMembershipIds(campaign),
            );
            setCampaignMemberships((currentMemberships) => ({
              ...currentMemberships,
              [campaign.id]: savedRows.map((recipient) => recipient.id),
            }));
            setCampaignMembershipDeliveries((currentDeliveries) => ({
              ...currentDeliveries,
              [campaign.id]: Object.fromEntries(
                savedRows.map((recipient) => [
                  recipient.id,
                  recipient.campaignDelivery ?? "not_sent",
                ]),
              ) as Record<string, CampaignDeliveryState>,
            }));
          }
          const sendScope = [
            campaign.id,
            mode,
            ...(selectedRecipientIds ?? []).slice().sort(),
          ].join(":");
          let sendIdempotencyKey = campaignSendIdempotencyKeysRef.current.get(sendScope);
          if (!sendIdempotencyKey) {
            sendIdempotencyKey = createCampaignSendIdempotencyKey();
            campaignSendIdempotencyKeysRef.current.set(sendScope, sendIdempotencyKey);
          }
          const result = await sendCampaignOnServer(campaign.id, {
            mode,
            recipientIds: selectedRecipientIds,
            idempotencyKey: sendIdempotencyKey,
          });
          campaignSendIdempotencyKeysRef.current.delete(sendScope);
          setCampaignSendResults((previousResults) => ({
            ...previousResults,
            [campaign.id]: result,
          }));
          const failureDetail = campaignSendFailureDetail(result);
          setCampaignMessage(
            `Campania a fost procesată: ${campaignSendResultSummary(result)}${
              failureDetail ? `. ${failureDetail}` : ""
            }.`,
          );
          await refreshWorkspace();
          startRapidRefresh();
        } catch (error) {
          setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi trimisă.");
        } finally {
          campaignSendingRef.current = null;
          setSendingCampaignId(null);
          setSendingCampaignMode(null);
        }
      },
    });
  };

  const handleSendCampaignRecipient = (
    campaign: EmailCampaign,
    recipient: CampaignRecipientRow,
    action: "send" | "resend",
  ) => {
    const readinessError = campaignSendReadinessError(campaign);
    if (readinessError) {
      setCampaignMessage(readinessError);
      return;
    }
    const recipientLabel = campaignRecipientName(recipient) || recipient.email;
    const isResend = action === "resend";
    setEmailConfirmDialog({
      title: isResend ? "Retrimiți acest email?" : "Trimiți acest email de test?",
      description: isResend
        ? `Campania „${campaign.name}” va fi retrimisă doar către ${recipientLabel}. Această acțiune trece explicit peste marcajul „Trimis”.`
        : `Campania „${campaign.name}” va fi trimisă doar către ${recipientLabel}. Ceilalți destinatari selectați rămân netrimiși.`,
      confirmLabel: isResend ? "Retrimite" : "Trimite",
      onConfirm: async () => {
        if (campaignSendingRef.current) return;
        campaignSendingRef.current = campaign.id;
        setSendingCampaignId(campaign.id);
        setSendingCampaignMode("selected");
        setSendingCampaignRecipientId(recipient.id);
        setCampaignMessage(null);
        try {
          const currentCapacity = await getEmailSendCapacity();
          setSendCapacity(currentCapacity);
          if (currentCapacity.remaining_today < 1) {
            throw new Error("Capacitatea de trimitere pentru astăzi a fost folosită.");
          }
          const result = await sendCampaignOnServer(campaign.id, {
            mode: "selected",
            recipientIds: [recipient.id],
            idempotencyKey: createCampaignSendIdempotencyKey(),
          });
          setCampaignSendResults((previousResults) => ({
            ...previousResults,
            [campaign.id]: result,
          }));
          const failureDetail = campaignSendFailureDetail(result);
          setCampaignMessage(failureDetail
            ? `Emailul către ${recipientLabel} nu a fost trimis. ${failureDetail}`
            : `${isResend ? "Retrimiterea" : "Trimiterea"} către ${recipientLabel} a fost procesată: ${campaignSendResultSummary(result)}.`);
          await refreshWorkspace();
          startRapidRefresh();
        } catch (error) {
          setCampaignMessage(
            error instanceof Error
              ? error.message
              : "Emailul nu a putut fi trimis.",
          );
        } finally {
          campaignSendingRef.current = null;
          setSendingCampaignId(null);
          setSendingCampaignMode(null);
          setSendingCampaignRecipientId(null);
        }
      },
    });
  };

  const handleDeleteCampaign = (campaign: EmailCampaign) => {
    setEmailConfirmDialog({
      title: "Ștergi campania?",
      description: `Campania „${campaign.name}” va fi ștearsă. Contactele și istoricul de livrare rămân păstrate.`,
      confirmLabel: "Șterge",
      tone: "danger",
      onConfirm: async () => {
        if (campaignDeletingRef.current) return;
        campaignDeletingRef.current = campaign.id;
        setDeletingCampaignId(campaign.id);
        setCampaignMessage(null);
        try {
          await deleteCampaignOnServer(campaign.id);
          const assetFileName = campaignAssetFileNameFromUrl(campaign.thumbnail_url);
          if (assetFileName) {
            try {
              await deleteCampaignAssetOnServer(assetFileName);
            } catch {
              setPendingCampaignAssetCleanup(assetFileName);
              setCampaignAssetMessage(
                "Campania a fost ștearsă, dar imaginea ei nu a putut fi eliminată. Reîncearcă.",
              );
            }
          }
          setCampaignSendResults((previousResults) => {
            const nextResults = { ...previousResults };
            delete nextResults[campaign.id];
            return nextResults;
          });
          setCampaignMemberships((previousMemberships) => {
            const nextMemberships = { ...previousMemberships };
            delete nextMemberships[campaign.id];
            return nextMemberships;
          });
          setCampaignMembershipSearches((previousSearches) => {
            const nextSearches = { ...previousSearches };
            delete nextSearches[campaign.id];
            return nextSearches;
          });
          setCampaignMembershipTypeFilters((previousFilters) => {
            const nextFilters = { ...previousFilters };
            delete nextFilters[campaign.id];
            return nextFilters;
          });
          setCampaignMessage("Campania a fost ștearsă.");
          await refreshWorkspace();
        } catch (error) {
          setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi ștearsă.");
        } finally {
          campaignDeletingRef.current = null;
          setDeletingCampaignId(null);
        }
      },
    });
  };

  // Search state
  const [searchQuery, setSearchQuery] = useState(get("q") ?? "");

  useEffect(() => {
    setSearchQuery(get("q") ?? "");
  }, [get, searchKey]);

  const filteredTemplates = React.useMemo(() => {
    const visibleTemplates = templates.filter((template) => !template.baseKey.startsWith("template_"));
    if (!searchQuery.trim()) return visibleTemplates;
    const q = searchQuery.toLowerCase();
    return visibleTemplates.filter((t) =>
      t.name.toLowerCase().includes(q) ||
      t.subject.toLowerCase().includes(q)
    );
  }, [templates, searchQuery]);
  const templatesById = useMemo(() => {
    const byId = new Map<string, EmailTemplate>();
    for (const template of templates) {
      byId.set(template.id, template);
    }
    return byId;
  }, [templates]);

  // Load templates from Server
  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    try {
      const list = await listEmailTemplatesOnServer();
      setTemplates(list);
      setEmailNoticeMessage(null);
    } catch (error) {
      setTemplates([]);
      setEmailNoticeMessage(error instanceof Error ? error.message : "Șabloanele nu au putut fi încărcate.");
    } finally {
      setIsLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Sync editor fields when selected template changes
  const selectedTemplate = templatesById.get(selectedTemplateId);
  const templateValidationMessage = selectedTemplate && isEditing
    ? emailTemplateDraftValidation({
      baseKey: selectedTemplate.baseKey,
      lane: editLane,
      subject: editSubject,
      body: `${editHeading}\n${editBody}`,
    })
    : null;
  useEffect(() => {
    if (selectedTemplate) {
      const draft = parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject);
      setEditSubject(selectedTemplate.subject);
      setEditHeading(draft.heading);
      setEditBody(draft.body);
      setEditLane(selectedTemplate.lane);
    }
  }, [selectedTemplate]);

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId || !selectedTemplate || templateOperationRef.current) return;
    if (templateValidationMessage) {
      setEmailNoticeMessage(templateValidationMessage);
      return;
    }
    templateOperationRef.current = "save";
    setTemplateOperation("save");
    setIsLoadingTemplates(true);
    try {
      const nextBody = buildStyledEmailTemplateBody({
        heading: editHeading,
        body: editBody,
        lane: editLane,
      });
      const nextTextBody = htmlToPlainText(nextBody);
      const updatedTemp: EmailTemplate = {
        ...selectedTemplate,
        subject: editSubject,
        body: nextBody,
        lane: editLane,
        textBody: nextTextBody,
        placeholders: detectedPlaceholders(
          editSubject,
          `${nextBody}\n${nextTextBody}`,
        ),
      };
      const saved = await updateEmailTemplateOnServer(updatedTemp);
      setIsEditing(false);
      setSelectedTemplateId(saved.id);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      setEmailNoticeMessage((e as Error).message ?? "Eroare la salvarea șablonului.");
    } finally {
      templateOperationRef.current = null;
      setTemplateOperation(null);
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplate = async () => {
    if (templateOperationRef.current) return;
    templateOperationRef.current = "create";
    setTemplateOperation("create");
    localTemplateCounterRef.current += 1;
    const existingTemplateKeys = new Set(templates.flatMap((template) => [template.id, template.baseKey]));
    let key = `template_local_${localTemplateCounterRef.current}`;

    while (existingTemplateKeys.has(key)) {
      localTemplateCounterRef.current += 1;
      key = `template_local_${localTemplateCounterRef.current}`;
    }

    const newTemp: EmailTemplate = {
      id: key,
      baseKey: key,
      version: 1,
      name: "Șablon Email Nou",
      subject: "Subiectul emailului {first_name}",
      lane: "transactional",
      placeholders: ["{first_name}", "{action_url}"],
      body: buildStyledEmailTemplateBody({
        heading: "Titlul din email",
        body: `Salut {first_name},\n\nIntroduceți conținutul noului șablon email aici. Puteți folosi coduri între acolade pentru personalizare.\n\n${DEFAULT_ACTION_TOKEN}`,
        lane: "transactional",
      }),
    };
    setIsLoadingTemplates(true);
    try {
      const saved = await createEmailTemplateOnServer(newTemp);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      setEmailNoticeMessage((e as Error).message ?? "Eroare la crearea șablonului.");
    } finally {
      templateOperationRef.current = null;
      setTemplateOperation(null);
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplateVersion = async () => {
    if (!selectedTemplate || templateOperationRef.current) return;
    templateOperationRef.current = "version";
    setTemplateOperation("version");
    setIsLoadingTemplates(true);
    try {
      const nextTemplate: EmailTemplate = {
        ...selectedTemplate,
        version: selectedTemplate.version + 1,
      };
      const saved = await createEmailTemplateOnServer(nextTemplate);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      setEmailNoticeMessage((e as Error).message ?? "Eroare la crearea versiunii noi.");
    } finally {
      templateOperationRef.current = null;
      setTemplateOperation(null);
      setIsLoadingTemplates(false);
    }
  };

  const handleDeleteTemplate = async () => {
    if (!selectedTemplate || templateOperationRef.current) return;
    if (templates.length <= 1) {
      setEmailNoticeMessage("Trebuie să păstrați cel puțin un șablon în catalog.");
      return;
    }

    setEmailConfirmDialog({
      title: "Pensionezi șablonul?",
      description: `Șablonul „${selectedTemplate.name}” va fi pensionat din catalog. Campaniile existente nu sunt modificate.`,
      confirmLabel: "Pensionează",
      tone: "danger",
      onConfirm: async () => {
        if (templateOperationRef.current) return;
        templateOperationRef.current = "delete";
        setTemplateOperation("delete");
        setIsLoadingTemplates(true);
        try {
          await deleteEmailTemplateOnServer(selectedTemplate.baseKey);
          const remaining = templates.filter((t) => t.baseKey !== selectedTemplate.baseKey);
          setTemplates(remaining);
          if (remaining.length > 0) {
            setSelectedTemplateId(remaining[0].id);
          } else {
            setSelectedTemplateId("");
          }
          setIsEditing(false);
        } catch (e) {
          setEmailNoticeMessage((e as Error).message ?? "Eroare la pensionarea șablonului.");
        } finally {
          templateOperationRef.current = null;
          setTemplateOperation(null);
          setIsLoadingTemplates(false);
        }
      },
    });
  };

  const getRenderedPreview = useCallback((
    subjectText: string,
    bodyText: string,
    lane: string,
    replacements: Record<string, string> = previewReplacements,
  ) => {
    let replacedSubject = subjectText;
    let replacedBody = bodyText;

    replacedSubject = replacePreviewPlaceholders(replacedSubject, replacements);
    replacedBody = replacePreviewPlaceholders(replacedBody, replacements);

    let html = renderEmailTemplatePreviewBody(replacedBody);

    if (lane === "campaign") {
      html = renderCampaignEmailPreviewShell(html, replacements);
    }

    return {
      subject: replacedSubject,
      bodyHtml: html,
    };
  }, [previewReplacements]);

  const preview = useMemo(
    () =>
      selectedTemplate
        ? getRenderedPreview(
            isEditing ? editSubject : selectedTemplate.subject,
            isEditing ? buildStyledEmailTemplateBody({
              heading: editHeading,
              body: editBody,
              lane: editLane,
            }) : selectedTemplate.body,
            isEditing ? editLane : selectedTemplate.lane,
          )
        : { subject: "", bodyHtml: "" },
    [editBody, editHeading, editLane, editSubject, getRenderedPreview, isEditing, selectedTemplate],
  );
  const campaignPreview = useMemo(
    () => getRenderedPreview(
      campaignSubject,
      campaignBody || selectedCampaignTemplate?.body || "",
      "campaign",
      campaignPreviewReplacements,
    ),
    [campaignBody, campaignPreviewReplacements, campaignSubject, getRenderedPreview, selectedCampaignTemplate],
  );

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-center justify-between gap-6 px-1 py-1">
        <h1 className="text-3xl font-semibold leading-tight tracking-normal text-foreground md:text-[2rem]">
          Comunicare
        </h1>
        <EmailWorkspaceNavigation activeView={activeWorkspaceView} onViewChange={setWorkspaceView} />
      </header>

      {activeTab === "campaigns" && (
        <div className="flex flex-col gap-5">
          <section
            className="overflow-hidden rounded-lg border border-[var(--border)] bg-surface text-foreground shadow-sm"
            aria-label={
              campaignView === "campaigns"
                ? "Campanii"
                : campaignView === "contacts"
                  ? "Contacte"
                  : "Arhivă contacte"
            }
          >
            <div className="flex flex-col gap-3 border-b border-[var(--border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-medium text-muted-foreground">
                {campaignView === "campaigns"
                  ? `${campaigns.length} ${campaigns.length === 1 ? "campanie" : "campanii"} · ${readyCampaignCount} ${readyCampaignCount === 1 ? "pregătită" : "pregătite"}`
                  : campaignView === "contacts"
                    ? `${activeCampaignContacts.length} contacte active`
                    : `${archivedCampaignRecipients.length} ${archivedCampaignRecipients.length === 1 ? "contact arhivat" : "contacte arhivate"}`}
              </p>
              <div className="flex flex-wrap gap-2 sm:justify-end">
                  {campaignView === "campaigns" ? (
                    <Button type="button" onClick={openCreateCampaignModal}>
                      <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                      Campanie nouă
                    </Button>
                  ) : null}
                  {campaignView === "contacts" ? (
                    <Button
                      type="button"
                      onClick={() => contactImportInputRef.current?.click()}
                      disabled={isUploadingCSV}
                    >
                      {isUploadingCSV ? (
                        <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} />
                      ) : (
                        <UploadIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                      )}
                      {isUploadingCSV ? "Importăm contactele" : "Importă contacte"}
                    </Button>
                  ) : null}
                  {campaignView === "contacts" ? (
                    <Input
                      ref={contactImportInputRef}
                      type="file"
                      accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      aria-label="Importă fișier contacte"
                      aria-hidden="true"
                      className="sr-only !size-px !min-w-0 !border-0 !p-0"
                      tabIndex={-1}
                      onChange={handleFileUpload}
                      disabled={isUploadingCSV}
                    />
                  ) : null}
                  {campaignView === "contacts" ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowManualAddModal(true);
                        setParams({ tab: "campaigns", modal: "add-contact" }, "push");
                      }}
                    >
                      <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                      Adaugă contact
                    </Button>
                  ) : null}
              </div>
            </div>
            {campaignMessage && !showCampaignModal ? (
              <InlineFeedback className="mx-6 mt-4 px-3 py-2" descriptionClassName="text-xs leading-5">
                {campaignMessage}
              </InlineFeedback>
            ) : null}
            {pendingCampaignAssetCleanup && campaignAssetMessage && !showCampaignModal ? (
              <InlineFeedback
                tone="danger"
                className="mx-6 mt-4 px-3 py-2"
                descriptionClassName="text-xs leading-5"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <span>{campaignAssetMessage}</span>
                  <Button
                    type="button"
                    size="xs"
                    variant="outline"
                    disabled={isRetryingCampaignAssetCleanup}
                    className="shrink-0"
                    onClick={() => void retryCampaignAssetCleanup()}
                  >
                    {isRetryingCampaignAssetCleanup ? "Eliminăm imaginea" : "Reîncearcă eliminarea"}
                  </Button>
                </div>
              </InlineFeedback>
            ) : null}
            {campaignView === "campaigns" ? (
              <CampaignsWorkspaceView
                campaigns={campaigns}
                isLoading={isLoadingCampaigns}
                memberships={campaignMemberships}
                membershipSearches={campaignMembershipSearches}
                membershipTypeFilters={campaignMembershipTypeFilters}
                membershipCompanySelections={campaignMembershipCompanySelections}
                membershipErrors={campaignMembershipErrors}
                sendResults={campaignSendResults}
                sendCapacity={sendCapacity}
                openCampaignId={openCampaignId}
                sendingCampaignId={sendingCampaignId}
                sendingMode={sendingCampaignMode}
                sendingRecipientId={sendingCampaignRecipientId}
                deletingCampaignId={deletingCampaignId}
                savingMembershipId={savingCampaignMembershipId}
                getActiveMemberIds={activeCampaignMembershipIds}
                getSendableMemberIds={sendableCampaignMembershipIds}
                getRecipientDelivery={campaignRecipientDelivery}
                isDeliveryLocked={campaignDeliveryIsLocked}
                getEligibleRecipients={campaignEligibleRecipients}
                getVisibleEligibleRecipients={visibleCampaignEligibleRecipients}
                setOpenCampaignId={setOpenCampaignId}
                setMembershipSearch={(campaignId, value) => setCampaignMembershipSearches((current) => ({ ...current, [campaignId]: value }))}
                setMembershipTypeFilter={(campaignId, value) => setCampaignMembershipTypeFilters((current) => ({ ...current, [campaignId]: value }))}
                setMembershipCompany={(campaignId, value) => setCampaignMembershipCompanySelections((current) => ({ ...current, [campaignId]: value }))}
                toggleMembershipRecipient={(campaign, recipientId) => void toggleCampaignMembershipRecipient(campaign, recipientId)}
                toggleMembershipCompany={toggleCampaignMembershipCompany}
                sendCampaign={(campaign, mode) => void handleSendCampaign(campaign, mode)}
                sendRecipient={handleSendCampaignRecipient}
                editCampaign={openEditCampaignModal}
                deleteCampaign={handleDeleteCampaign}
              />
            ) : campaignView === "contacts" ? (
              <ContactsWorkspaceView
                message={campaignContactMessage}
                contacts={visibleCampaignContacts}
                inactiveCount={inactiveCampaignContacts.length}
                search={campaignContactSearch}
                typeFilter={campaignContactTypeFilter}
                showInactive={showInactiveCampaignContacts}
                selectedIds={selectedCampaignRecipientIds}
                visibleSelectedIds={visibleSelectedCampaignRecipientIds}
                selectableIds={selectableCampaignRecipientIdSet}
                visibleSelectableIds={visibleSelectableCampaignRecipientIds}
                allVisibleSelected={visibleContactsAllSelected}
                selectedContactBeingEdited={isSelectedCampaignContactBeingEdited}
                bulkAction={bulkContactAction}
                editingContactId={editingContactId}
                drafts={contactDrafts}
                savingContactId={savingContactId}
                deletingContactId={deletingContactId}
                setSearch={setCampaignContactSearch}
                setTypeFilter={setCampaignContactTypeFilter}
                toggleAllVisible={toggleAllVisibleCampaignRecipients}
                toggleInactive={toggleInactiveCampaignContacts}
                updateSelectedStatus={(status) => void updateSelectedCampaignContactsStatus(status)}
                deleteSelected={() => void deleteSelectedCampaignContacts()}
                toggleSelected={toggleSelectedCampaignRecipient}
                updateDraft={updateContactDraft}
                saveContact={(recipient) => void saveContact(recipient)}
                cancelEditing={cancelEditingContact}
                startEditing={startEditingContact}
                deleteContact={deleteContact}
                openManualContact={() => {
                  setShowManualAddModal(true);
                  setParams({ tab: "campaigns", modal: "add-contact" }, "push");
                }}
              />
            ) : (
              <ArchivedContactsWorkspaceView
                message={campaignContactMessage}
                contacts={visibleArchivedCampaignContacts}
                search={archiveContactSearch}
                action={archiveContactAction}
                setSearch={setArchiveContactSearch}
                restoreContact={(recipient) => void restoreArchivedContact(recipient)}
                deleteContact={permanentlyDeleteArchivedContact}
              />
            )}
          </section>
        </div>
      )}

      {activeTab === "templates" ? (
        <TemplatesWorkspaceView
          selectedTemplateId={selectedTemplateId}
          selectedTemplate={selectedTemplate}
          filteredTemplates={filteredTemplates}
          templateCount={templates.length}
          searchQuery={searchQuery}
          isEditing={isEditing}
          isLoading={isLoadingTemplates}
          operation={templateOperation}
          editSubject={editSubject}
          editHeading={editHeading}
          editBody={editBody}
          editLane={editLane}
          preview={preview}
          previewCalendlyUrl={previewCalendlyUrl}
          validationMessage={templateValidationMessage}
          onSearchChange={(value) => {
            setSearchQuery(value);
            setParam("q", value, "replace");
          }}
          onSelectTemplate={setSelectedTemplateId}
          onCreate={handleCreateTemplate}
          onSave={handleSaveTemplate}
          onCreateVersion={handleCreateTemplateVersion}
          onDelete={handleDeleteTemplate}
          setIsEditing={setIsEditing}
          setEditSubject={setEditSubject}
          setEditHeading={setEditHeading}
          setEditBody={setEditBody}
          setEditLane={setEditLane}
          setPreviewCalendlyUrl={setPreviewCalendlyUrl}
        />
      ) : null}

      <CampaignEditorModal
        open={showCampaignModal}
        editingCampaign={editingCampaign}
        campaignName={campaignName}
        campaignSegment={campaignSegment}
        campaignTemplateId={campaignTemplateId}
        campaignTemplates={campaignTemplates}
        campaignSubject={campaignSubject}
        campaignBody={campaignBody}
        campaignPlainBody={campaignPlainBody}
        campaignVideoUrl={campaignVideoUrl}
        campaignLandingUrl={campaignLandingUrl}
        campaignThumbnailUrl={campaignThumbnailUrl}
        campaignFieldErrors={campaignFieldErrors}
        campaignAssetMessage={campaignAssetMessage}
        hasPendingAssetCleanup={Boolean(pendingCampaignAssetCleanup)}
        isRetryingAssetCleanup={isRetryingCampaignAssetCleanup}
        campaignAssetPreviewUrl={campaignAssetPreviewUrl}
        campaignMediaHasChanges={campaignMediaHasChanges}
        campaignPreview={campaignPreview}
        campaignMessage={campaignMessage}
        campaignSaveFailure={campaignSaveFailure}
        isSaving={isCreatingCampaign}
        isUploadingAsset={isUploadingCampaignAsset}
        assetInputRef={campaignAssetInputRef}
        onClose={closeCampaignModal}
        onSubmit={handleSaveCampaign}
        onAssetChange={handleCampaignAssetUpload}
        clearPendingAsset={clearPendingCampaignAsset}
        retryAssetCleanup={() => void retryCampaignAssetCleanup()}
        clearFieldError={clearCampaignFieldError}
        setCampaignName={setCampaignName}
        setCampaignSegment={setCampaignSegment}
        setCampaignTemplateId={setCampaignTemplateId}
        setCampaignSubject={setCampaignSubject}
        setCampaignBody={setCampaignBody}
        setCampaignPlainBody={setCampaignPlainBody}
        setCampaignVideoUrl={setCampaignVideoUrl}
        setCampaignLandingUrl={setCampaignLandingUrl}
        setCampaignThumbnailUrl={setCampaignThumbnailUrl}
        setCampaignAssetMessage={setCampaignAssetMessage}
      />

      <ContactImportModal
        drafts={importDrafts}
        sheetName={importSheetName}
        activeCount={activeImportDraftCount}
        invalidCount={invalidImportDraftCount}
        duplicateCount={duplicateImportDraftEmailCount}
        isImporting={isImportingContacts}
        onCancel={() => {
          setImportDrafts([]);
          setImportSheetName(null);
        }}
        onConfirm={confirmCampaignRecipientImport}
        onDraftChange={updateImportDraft}
      />
      <ManualContactModal
        open={showManualAddModal}
        email={manualEmail}
        name={manualName}
        company={manualCompany}
        segment={manualSegment}
        isSaving={isAddingManual}
        onClose={closeManualAddModal}
        onSubmit={handleAddManualContact}
        setEmail={setManualEmail}
        setName={setManualName}
        setCompany={setManualCompany}
        setSegment={setManualSegment}
      />
      {emailConfirmDialog ? (
        <ModalLayer
          labelledBy="email-confirm-title"
          onClose={() => setEmailConfirmDialog(null)}
          panelClassName="max-w-md"
        >
          <div className="flex flex-col gap-4">
            <div>
              <h2 id="email-confirm-title" className="text-lg font-bold text-foreground">
                {emailConfirmDialog.title}
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{emailConfirmDialog.description}</p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEmailConfirmDialog(null)}
              >
                Anulează
              </Button>
              <Button
                type="button"
                variant={emailConfirmDialog.tone === "danger" ? "destructive" : "default"}
                size="sm"
                onClick={() => {
                  const action = emailConfirmDialog.onConfirm;
                  setEmailConfirmDialog(null);
                  void action();
                }}
              >
                {emailConfirmDialog.confirmLabel}
              </Button>
            </div>
          </div>
        </ModalLayer>
      ) : null}
      {emailNoticeMessage ? (
        <ModalLayer
          labelledBy="email-notice-title"
          onClose={() => setEmailNoticeMessage(null)}
          panelClassName="max-w-md"
        >
          <div className="flex flex-col gap-4">
            <div>
              <h2 id="email-notice-title" className="text-lg font-bold text-foreground">
                Atenție
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{emailNoticeMessage}</p>
            </div>
            <div className="flex justify-end border-t border-border pt-3">
              <Button
                type="button"
                onClick={() => setEmailNoticeMessage(null)}
              >
                Am înțeles
              </Button>
            </div>
          </div>
        </ModalLayer>
      ) : null}
    </div>
  );
}
