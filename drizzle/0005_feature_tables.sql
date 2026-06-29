CREATE TABLE `antibiotics` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`code` text,
	`class` text,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE UNIQUE INDEX `antibiotics_code_unique` ON `antibiotics` (`code`);--> statement-breakpoint
CREATE TABLE `calculated_tests` (
	`id` text PRIMARY KEY NOT NULL,
	`test_code` text NOT NULL,
	`name` text NOT NULL,
	`formula` text NOT NULL,
	`unit` text,
	`active` integer DEFAULT true,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `calculated_tests_test_code_unique` ON `calculated_tests` (`test_code`);--> statement-breakpoint
CREATE TABLE `critical_value_acknowledgments` (
	`id` text PRIMARY KEY NOT NULL,
	`notification_id` text NOT NULL,
	`acknowledged_by` text NOT NULL,
	`acknowledged_at` text NOT NULL,
	`notified_clinician` text,
	`notification_method` text,
	`notes` text,
	`escalated_to` text
);
--> statement-breakpoint
CREATE TABLE `critical_value_notifications` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`patient_id` text NOT NULL,
	`test_id` text NOT NULL,
	`test_code` text NOT NULL,
	`value` text NOT NULL,
	`threshold` text NOT NULL,
	`critical_type` text NOT NULL,
	`status` text DEFAULT 'Pending' NOT NULL,
	`created_at` text NOT NULL,
	`created_by` text
);
--> statement-breakpoint
CREATE TABLE `delta_check_flags` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`test_id` text NOT NULL,
	`rule_id` text NOT NULL,
	`previous_order_id` text,
	`previous_value` real,
	`current_value` real NOT NULL,
	`delta_percent` real,
	`delta_absolute` real,
	`flagged_at` text NOT NULL,
	`acknowledged_by` text,
	`acknowledged_at` text
);
--> statement-breakpoint
CREATE TABLE `delta_check_rules` (
	`id` text PRIMARY KEY NOT NULL,
	`test_id` text NOT NULL,
	`test_code` text NOT NULL,
	`delta_type` text NOT NULL,
	`threshold` real NOT NULL,
	`direction` text DEFAULT 'any' NOT NULL,
	`enabled` integer DEFAULT true,
	`created_at` text NOT NULL,
	`created_by` text
);
--> statement-breakpoint
CREATE TABLE `demographic_reference_ranges` (
	`id` text PRIMARY KEY NOT NULL,
	`test_id` text NOT NULL,
	`test_code` text NOT NULL,
	`age_min` integer,
	`age_max` integer,
	`gender` text DEFAULT 'All',
	`pregnancy` integer DEFAULT false,
	`trimester` integer,
	`low_normal` real,
	`high_normal` real,
	`low_critical` real,
	`high_critical` real,
	`unit` text,
	`notes` text,
	`active` integer DEFAULT true,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `distribution_logs` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`rule_id` text,
	`method` text NOT NULL,
	`destination` text,
	`sent_at` text,
	`status` text DEFAULT 'Pending' NOT NULL,
	`error` text
);
--> statement-breakpoint
CREATE TABLE `distribution_rules` (
	`id` text PRIMARY KEY NOT NULL,
	`requester_id` text,
	`test_id` text,
	`method` text NOT NULL,
	`destination` text,
	`auto_release` integer DEFAULT false,
	`active` integer DEFAULT true,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `documents` (
	`id` text PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`category` text NOT NULL,
	`version` text NOT NULL,
	`status` text NOT NULL,
	`file_path` text NOT NULL,
	`uploaded_by` text,
	`uploaded_at` text,
	`effective_date` text
);
--> statement-breakpoint
CREATE TABLE `email_queue` (
	`id` text PRIMARY KEY NOT NULL,
	`recipient` text NOT NULL,
	`subject` text NOT NULL,
	`body` text,
	`attachment_path` text,
	`status` text DEFAULT 'Pending',
	`attempts` integer DEFAULT 0,
	`created_at` text NOT NULL,
	`sent_at` text,
	`error` text
);
--> statement-breakpoint
CREATE TABLE `epidemiology_notifications` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`patient_id` text NOT NULL,
	`condition_id` text NOT NULL,
	`detected_at` text NOT NULL,
	`status` text DEFAULT 'Pending' NOT NULL,
	`reviewed_by` text,
	`reviewed_at` text,
	`submitted_by` text,
	`submitted_at` text,
	`notes` text
);
--> statement-breakpoint
CREATE TABLE `equipment` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`type` text NOT NULL,
	`serial_number` text,
	`manufacturer` text,
	`department` text,
	`status` text DEFAULT 'Active' NOT NULL,
	`last_service_date` text,
	`next_service_date` text,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE TABLE `equipment_logs` (
	`id` text PRIMARY KEY NOT NULL,
	`equipment_id` text NOT NULL,
	`type` text NOT NULL,
	`description` text NOT NULL,
	`performed_by` text NOT NULL,
	`timestamp` text NOT NULL,
	`outcome` text,
	FOREIGN KEY (`equipment_id`) REFERENCES `equipment`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `feedback` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`type` text NOT NULL,
	`message` text NOT NULL,
	`status` text DEFAULT 'New',
	`timestamp` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `histo_blocks` (
	`id` text PRIMARY KEY NOT NULL,
	`specimen_id` text NOT NULL,
	`block_id` text NOT NULL,
	`tissue_type` text,
	`status` text NOT NULL,
	`timestamp` text,
	FOREIGN KEY (`specimen_id`) REFERENCES `specimens`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `histo_blocks_block_id_unique` ON `histo_blocks` (`block_id`);--> statement-breakpoint
CREATE TABLE `histo_slides` (
	`id` text PRIMARY KEY NOT NULL,
	`block_id` text NOT NULL,
	`slide_id` text NOT NULL,
	`stain` text NOT NULL,
	`status` text NOT NULL,
	`timestamp` text,
	FOREIGN KEY (`block_id`) REFERENCES `histo_blocks`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `histo_slides_slide_id_unique` ON `histo_slides` (`slide_id`);--> statement-breakpoint
CREATE TABLE `loinc_codes` (
	`id` text PRIMARY KEY NOT NULL,
	`loinc_code` text NOT NULL,
	`long_name` text NOT NULL,
	`short_name` text,
	`component` text,
	`property` text,
	`time_aspect` text,
	`system` text,
	`scale` text,
	`method` text,
	`status` text DEFAULT 'Active'
);
--> statement-breakpoint
CREATE UNIQUE INDEX `loinc_codes_loinc_code_unique` ON `loinc_codes` (`loinc_code`);--> statement-breakpoint
CREATE TABLE `messages` (
	`id` text PRIMARY KEY NOT NULL,
	`sender` text NOT NULL,
	`recipient` text,
	`subject` text NOT NULL,
	`body` text NOT NULL,
	`read` integer DEFAULT false,
	`timestamp` text NOT NULL,
	`related_entity_id` text,
	`related_entity_type` text
);
--> statement-breakpoint
CREATE TABLE `micro_cultures` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`specimen_id` text NOT NULL,
	`test_id` text NOT NULL,
	`status` text NOT NULL,
	`incubator_location` text,
	`setup_time` text,
	`preliminary_result` text,
	`final_result` text,
	FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`specimen_id`) REFERENCES `specimens`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `notifiable_conditions` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`organism` text,
	`test_ids` text,
	`reporting_body` text NOT NULL,
	`timeframe` text DEFAULT '24h' NOT NULL,
	`active` integer DEFAULT true,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `phlebotomy_schedules` (
	`id` text PRIMARY KEY NOT NULL,
	`patient_id` text NOT NULL,
	`order_id` text,
	`ward_location` text NOT NULL,
	`scheduled_at` text NOT NULL,
	`collection_type` text DEFAULT 'Routine' NOT NULL,
	`test_ids` text,
	`assigned_to` text,
	`status` text DEFAULT 'Scheduled' NOT NULL,
	`notes` text,
	`completed_at` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `production_runs` (
	`id` text PRIMARY KEY NOT NULL,
	`recipe_id` text NOT NULL,
	`batch_number` text NOT NULL,
	`status` text NOT NULL,
	`quantity` integer NOT NULL,
	`start_date` text,
	`completion_date` text,
	`expiry_date` text,
	`operator` text,
	FOREIGN KEY (`recipe_id`) REFERENCES `recipes`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `production_runs_batch_number_unique` ON `production_runs` (`batch_number`);--> statement-breakpoint
CREATE TABLE `qc_definitions` (
	`id` text PRIMARY KEY NOT NULL,
	`material_id` text NOT NULL,
	`test_code` text NOT NULL,
	`test_name` text NOT NULL,
	`mean` real NOT NULL,
	`sd` real NOT NULL,
	`unit` text NOT NULL,
	FOREIGN KEY (`material_id`) REFERENCES `qc_materials`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `qc_materials` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`lot_number` text NOT NULL,
	`expiration_date` text NOT NULL,
	`manufacturer` text,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE TABLE `qc_runs` (
	`id` text PRIMARY KEY NOT NULL,
	`definition_id` text NOT NULL,
	`value` real NOT NULL,
	`result_flags` text,
	`status` text NOT NULL,
	`performed_by` text NOT NULL,
	`timestamp` text NOT NULL,
	`comments` text,
	FOREIGN KEY (`definition_id`) REFERENCES `qc_definitions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `recipes` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`ingredients` text,
	`instructions` text,
	`yield` text,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE TABLE `record_locks` (
	`id` text PRIMARY KEY NOT NULL,
	`entity_type` text NOT NULL,
	`entity_id` text NOT NULL,
	`user_id` text NOT NULL,
	`username` text NOT NULL,
	`timestamp` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `reflex_activations` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`rule_id` text NOT NULL,
	`trigger_value` text NOT NULL,
	`new_test_id` text NOT NULL,
	`triggered_at` text NOT NULL,
	`status` text DEFAULT 'Pending' NOT NULL
);
--> statement-breakpoint
CREATE TABLE `reflex_rules` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`trigger_test_id` text NOT NULL,
	`trigger_condition` text NOT NULL,
	`add_test_id` text NOT NULL,
	`add_test_code` text NOT NULL,
	`enabled` integer DEFAULT true,
	`created_at` text NOT NULL,
	`created_by` text
);
--> statement-breakpoint
CREATE TABLE `rejection_criteria` (
	`id` text PRIMARY KEY NOT NULL,
	`reason` text NOT NULL,
	`description` text,
	`category` text DEFAULT 'General',
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE TABLE `requesters` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`type` text NOT NULL,
	`contact_name` text,
	`email` text,
	`phone` text,
	`fax` text,
	`address` text,
	`delivery_preference` text DEFAULT 'portal',
	`active` integer DEFAULT true,
	`created_at` text NOT NULL,
	`notes` text
);
--> statement-breakpoint
CREATE TABLE `result_signatures` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`signed_by` text NOT NULL,
	`signed_at` text NOT NULL,
	`signature_type` text NOT NULL,
	`ip_address` text,
	`user_agent` text
);
--> statement-breakpoint
CREATE TABLE `retention_policies` (
	`id` text PRIMARY KEY NOT NULL,
	`specimen_type` text NOT NULL,
	`retention_days` integer NOT NULL,
	`temperature` text,
	`disposal_method` text DEFAULT 'Biohazard Disposal' NOT NULL,
	`active` integer DEFAULT true,
	`notes` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `routing_assignments` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`test_id` text NOT NULL,
	`workstation_id` text NOT NULL,
	`status` text NOT NULL,
	`timestamp` text NOT NULL,
	FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`workstation_id`) REFERENCES `workstations`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `routing_rules` (
	`id` text PRIMARY KEY NOT NULL,
	`test_id` text NOT NULL,
	`workstation_id` text,
	`department_id` text,
	`conditions` text,
	`priority` integer DEFAULT 0,
	`active` integer DEFAULT true
);
--> statement-breakpoint
CREATE TABLE `settings` (
	`id` text PRIMARY KEY NOT NULL,
	`key` text NOT NULL,
	`value` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `settings_key_unique` ON `settings` (`key`);--> statement-breakpoint
CREATE TABLE `specimen_disposals` (
	`id` text PRIMARY KEY NOT NULL,
	`specimen_id` text NOT NULL,
	`policy_id` text,
	`disposed_at` text NOT NULL,
	`disposed_by` text NOT NULL,
	`batch_number` text,
	`notes` text
);
--> statement-breakpoint
CREATE TABLE `specimen_receiving` (
	`id` text PRIMARY KEY NOT NULL,
	`specimen_id` text NOT NULL,
	`order_id` text NOT NULL,
	`received_at` text NOT NULL,
	`received_by` text NOT NULL,
	`condition` text DEFAULT 'Acceptable' NOT NULL,
	`condition_notes` text,
	`rejection_reason` text,
	`temperature` text,
	`volume` real,
	`status` text DEFAULT 'Accepted' NOT NULL
);
--> statement-breakpoint
CREATE TABLE `tat_breaches` (
	`id` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`actual_hours` real NOT NULL,
	`target_hours` real NOT NULL,
	`breach_type` text NOT NULL,
	`detected_at` text NOT NULL,
	`resolved_at` text,
	`notified_at` text
);
--> statement-breakpoint
CREATE TABLE `tat_thresholds` (
	`id` text PRIMARY KEY NOT NULL,
	`scope` text NOT NULL,
	`scope_id` text,
	`target_hours` real NOT NULL,
	`warning_hours` real NOT NULL,
	`breach_hours` real NOT NULL,
	`priority` text DEFAULT 'Routine',
	`active` integer DEFAULT true,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `user_competencies` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`test_id` text,
	`category` text,
	`competency_date` text NOT NULL,
	`expiry_date` text NOT NULL,
	`assessed_by` text NOT NULL,
	`status` text DEFAULT 'Active' NOT NULL,
	`notes` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `worksheets` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`department` text NOT NULL,
	`test_ids` text,
	`status` text,
	`created_at` text,
	`created_by` text
);
--> statement-breakpoint
CREATE TABLE `workstations` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`department` text NOT NULL,
	`ip_address` text,
	`printer_id` text,
	`instrument_ids` text,
	`active` integer DEFAULT true
);
